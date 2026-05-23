from fastapi import FastAPI, Depends, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
from pathlib import Path

import hashlib
import os
import json
from difflib import SequenceMatcher
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any

# Keep the package import root available for local uvicorn runs.
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))

from apps.admin_center.backend.mongo_store import AdminMongoStore
from apps.admin_center.backend.mhtml_processor import MHTMLProcessor
from apps.admin_center.backend.auth import clear_session, create_session, login_key, login_rate_limiter, session_from_request, verify_password
from apps.admin_center.backend.rule_catalog import rule_summaries, seed_structures, target_fields, targets_for
from apps.admin_center.backend.schemas import DedupDecisionSchema, ExtractionPreviewSchema, ExtractionRulePatchSchema, LoginSchema, SourceSchema
from apps.admin_center.backend.services import (
    dedup_candidate_id,
    field_preview,
    model_dump,
    normalize_product_name,
    safe_rule_domain,
    source_group,
)
from apps.admin_center.backend.settings import settings

mongo_store = AdminMongoStore()

app = FastAPI(title="Admin Center API", version="1.0.0")

cors_origins = [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

structures_dir = Path(__file__).resolve().parent / "structures"
admin_store_dir = project_root / "store" / "admin"
dedup_queue_path = admin_store_dir / "dedup_queue.json"


def require_mongo_ready() -> None:
    if not mongo_store.ready():
        raise HTTPException(status_code=503, detail="MongoDB Atlas is not ready for Admin Center mutations")


def require_mutation_session(request: Request) -> str:
    role = session_from_request(request)["role"]
    require_mongo_ready()
    return role


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _raw_dirs(domain: str | None = None) -> list[Path]:
    raw_dir = project_root / "store" / "raw"
    if not domain:
        return [raw_dir] if raw_dir.exists() else []
    aliases = {domain, domain.removeprefix("www.")}
    if not domain.startswith("www."):
        aliases.add(f"www.{domain}")
    return [raw_dir / alias for alias in aliases if (raw_dir / alias).exists()]


def _artifact_id(path: Path) -> str:
    relative = path.relative_to(project_root).as_posix()
    return hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16]


def _meta_for_raw(path: Path) -> dict[str, Any]:
    meta_path = Path(f"{path}.meta.json")
    if meta_path.exists():
        try:
            return _read_json(meta_path)
        except Exception:
            return {}
    return {}


def _raw_artifact_record(path: Path) -> dict[str, Any]:
    meta = _meta_for_raw(path)
    return {
        "id": _artifact_id(path),
        "filename": path.name,
        "path": str(path.relative_to(project_root)),
        "domain": path.parent.name,
        "task_id": path.name,
        "url": meta.get("url"),
        "page_type": meta.get("page_type", "unknown"),
        "size": path.stat().st_size,
        "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
    }


def _raw_artifacts(domain: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
    mongo_artifacts = mongo_store.raw_pages(domain, limit)
    if mongo_artifacts:
        return mongo_artifacts

    files = []
    for root in _raw_dirs(domain):
        files.extend(root.glob("**/*.mhtml"))
    files.sort(key=os.path.getmtime, reverse=True)
    return [_raw_artifact_record(path) for path in files[:limit]]


def _raw_artifact_path(artifact_id: str | None, domain: str | None = None) -> Path | None:
    if not artifact_id:
        artifacts = _raw_artifacts(domain, limit=1)
        return project_root / artifacts[0]["path"] if artifacts else None
    for artifact in _raw_artifacts(domain, limit=500):
        if artifact["id"] == artifact_id:
            return project_root / artifact["path"]
    raise HTTPException(status_code=404, detail="Raw artifact not found")


def _raw_artifact_html(artifact_id: str | None, domain: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    raw_doc = mongo_store.raw_page(artifact_id, domain)
    if raw_doc:
        return mongo_store._raw_page_view(raw_doc), mongo_store.raw_page_html(raw_doc)
    raw_file = _raw_artifact_path(artifact_id, domain)
    if raw_file is None:
        return None, None
    return _raw_artifact_record(raw_file), MHTMLProcessor.decode_file(raw_file)


def _job_status_label(status: str | None) -> str:
    normalized = (status or "pending").strip().lower()
    return {
        "pending": "Pending",
        "processing": "Processing",
        "completed": "Completed",
        "failed": "Failed",
    }.get(normalized, normalized.title() or "Pending")


def _load_output_products(limit: int = 600) -> list[dict[str, Any]]:
    products = mongo_store.list_products(limit=limit)
    if products:
        return products

    products = []
    output_dir = project_root / "store" / "outputs"
    if not output_dir.exists():
        return products

    for path in sorted(output_dir.glob("**/*.json"), key=os.path.getmtime, reverse=True):
        try:
            data = _read_json(path)
        except Exception:
            continue
        source = data.get("source_site") or path.stem.split("_")[0]
        for product in data.get("products", []):
            name = product.get("name") or product.get("product_name")
            if not name:
                continue
            products.append({
                "name": name,
                "source": source,
                "price": product.get("price", product.get("price_numeric", 0)),
                "url": product.get("url") or product.get("product_url"),
                "brand": product.get("brand"),
                "category": product.get("category", "Khác"),
                "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
            })
            if len(products) >= limit:
                return products
    return products


def _dedup_candidates(limit: int) -> list[dict[str, Any]]:
    products = _load_output_products()
    candidates = []
    checked = set()
    for index, left in enumerate(products):
        left_name = normalize_product_name(left["name"])
        if not left_name:
            continue
        for right in products[index + 1:]:
            right_name = normalize_product_name(right["name"])
            pair_id = dedup_candidate_id(left, right)
            if pair_id in checked or not right_name:
                continue
            checked.add(pair_id)
            score = SequenceMatcher(None, left_name, right_name).ratio()
            same_url = bool(left.get("url") and left.get("url") == right.get("url"))
            same_name = left_name == right_name
            if not (same_url or same_name or score >= 0.78):
                continue
            confidence = 0.99 if same_url else 0.96 if same_name else round(score, 2)
            reasons = []
            if same_name:
                reasons.append("normalized_name")
            if same_url:
                reasons.append("product_url")
            if score >= 0.78 and not same_name:
                reasons.append("name_similarity")
            candidates.append({
                "id": pair_id,
                "confidence": confidence,
                "reasons": reasons,
                "left": left,
                "right": right
            })
    candidates.sort(key=lambda row: row["confidence"], reverse=True)
    return candidates[:limit]


def _dedup_queue() -> dict[str, Any]:
    candidates = _dedup_candidates(200)
    mongo_store.sync_dedup_candidates(candidates)
    rows = mongo_store.list_dedup_candidates("all", 500)
    if rows:
        return {"candidates": {row["id"]: row for row in rows}}
    queue = _read_json(dedup_queue_path) if dedup_queue_path.exists() else {"candidates": {}}
    queue.setdefault("candidates", {})
    now = datetime.now(timezone.utc).isoformat()
    for candidate in candidates:
        existing = queue["candidates"].get(candidate["id"], {})
        queue["candidates"][candidate["id"]] = {
            **candidate,
            "status": existing.get("status", "pending"),
            "note": existing.get("note"),
            "created_at": existing.get("created_at", now),
            "updated_at": existing.get("updated_at", now),
        }
    _write_json(dedup_queue_path, queue)
    return queue


def _audit_rule(domain: str, target: str, role: str, version: str, artifact_id: str | None) -> None:
    event = {
        "event": "rule_patch",
        "domain": domain,
        "target": target,
        "role": role,
        "version": version,
        "raw_artifact_id": artifact_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mongo_store.record_rule_event(event)


def _seed_extraction_rules() -> None:
    mongo_store.seed_rule_structures(seed_structures(structures_dir))


def _price_history_months(lookback_days: int = 400) -> list[dict[str, Any]]:
    return mongo_store.price_history_months(lookback_days)


def _market_stats() -> dict[str, Any]:
    return mongo_store.market_stats()


# --- Job Monitor ---
@app.get("/api/jobs")
async def get_jobs(limit: int = 50):
    """Lấy danh sách các tệp đang xử lý và trạng thái của chúng"""
    mongo_jobs = mongo_store.jobs(limit)
    if mongo_jobs:
        return mongo_jobs

    jobs = []
    raw_dir = project_root / "store" / "raw"
    output_dir = project_root / "store" / "outputs"

    if not raw_dir.exists():
        return []

    output_files = [f.name for f in output_dir.glob("*.json")] if output_dir.exists() else []
    raw_files = list(raw_dir.glob("**/*.meta.json"))
    for meta_file in raw_files:
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            filename = meta_file.name.replace(".meta.json", "")
            source = meta.get("domain", meta_file.parent.name)
            is_completed = any(filename in of for of in output_files)
            status = "Completed" if is_completed else "Pending"
            if (meta_file.parent / f"{filename}.error").exists():
                status = "Failed"
            timestamp = datetime.fromtimestamp(os.path.getmtime(meta_file)).isoformat()

            jobs.append({
                "id": filename,
                "filename": filename,
                "source": source,
                "status": status,
                "timestamp": timestamp
            })
        except:
            continue

    jobs.sort(key=lambda x: x["timestamp"], reverse=True)
    return jobs[:limit]


@app.get("/api/jobs/logs/{job_id}")
async def get_job_logs(job_id: str):
    """Lấy log chi tiết của một Job từ Filesystem"""
    mongo_log = mongo_store.job_log(job_id)
    if mongo_log:
        return mongo_log

    raw_dir = project_root / "store" / "raw"
    output_dir = project_root / "store" / "outputs"

    logs = {"job_id": job_id, "events": [], "metadata": {}, "error": None, "output_summary": None}

    meta_files = list(raw_dir.glob(f"**/{job_id}.meta.json"))
    if meta_files:
        meta_file = meta_files[0]
        logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(meta_file)).isoformat()}] Raw file discovered.")
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                logs["metadata"] = json.load(f)
        except: pass

        error_file = meta_file.parent / f"{job_id}.error"
        if error_file.exists():
            with open(error_file, 'r', encoding='utf-8') as f:
                logs["error"] = f.read()
            logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(error_file)).isoformat()}] ❌ Processing failed.")

    output_files = list(output_dir.glob(f"{job_id}*.json"))
    if output_files:
        out_f = output_files[0]
        logs["events"].append(f"[{datetime.fromtimestamp(os.path.getmtime(out_f)).isoformat()}] ✅ Extraction completed.")
        try:
            with open(out_f, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logs["output_summary"] = {"product_count": len(data.get("products", [])), "source": data.get("source_site")}
        except: pass

    if not logs["events"]:
        return {"error": "Job not found"}
    return logs


# --- Monitoring Routes ---

@app.get("/api/dashboard/stats")
async def get_global_stats():
    stats = {
        "products": mongo_store.product_stats(),
        "files": mongo_store.job_counts(),
        "system": {"db_status": "MongoDB Atlas", "storage": "MongoDB raw pages / GridFS"}
    }

    if not stats["products"]["total"]:
        output_dir = project_root / "store" / "outputs"
        if output_dir.exists():
            stats["products"]["total"] = len(list(output_dir.glob("*.json")))

    if not sum(stats["files"].values()):
        raw_dir2 = project_root / "store" / "raw"
        output_dir2 = project_root / "store" / "outputs"
        all_meta = list(raw_dir2.glob("**/*.meta.json")) if raw_dir2.exists() else []
        all_outputs = list(output_dir2.glob("*.json")) if output_dir2.exists() else []
        stats["files"]["completed"] = len(all_outputs)
        stats["files"]["pending"] = max(0, len(all_meta) - len(all_outputs))
        stats["files"]["failed"] = len(list(raw_dir2.glob("**/*.error"))) if raw_dir2.exists() else 0

    stats["market"] = _market_stats()

    return stats


@app.get("/api/dashboard/trends")
async def get_price_trends():
    """Return monthly price observations from Mongo offers."""
    return _price_history_months()


@app.get("/api/dashboard/comparison")
async def get_source_comparison():
    """Return source-level average prices from stored product data."""
    return mongo_store.source_price_comparison()


@app.get("/api/dashboard/recent-products")
async def get_recent_products(limit: int = 10, source: str = None):
    result = mongo_store.recent_products(limit, source)
    if result:
        return result

    products = []
    output_dir = project_root / "store" / "outputs"
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                with open(f, 'r', encoding='utf-8') as j:
                    data = json.load(j)
                    source_site = data.get("source_site", f.stem.split('_')[0])
                    if source and source != "all" and source_site != source:
                        continue
                    for p in data.get("products", [])[:2]:
                        products.append({
                            "name": p.get("name"),
                            "price_numeric": p.get("price"),
                            "currency": "VND",
                            "source_site": source_site,
                            "url": p.get("url"),
                            "updated_at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
                        })
            except:
                continue
    return products[:limit]


@app.get("/api/dashboard/sources")
async def get_sources():
    result = mongo_store.product_sources()
    if len(result) > 1:
        return result

    raw_dir = project_root / "store" / "raw"
    sources = ["all"]
    if raw_dir.exists():
        for d in raw_dir.iterdir():
            if d.is_dir() and d.name != "misc":
                sources.append(d.name)
    return sources


# --- Master Data: Sản phẩm tổng hợp ---
@app.get("/api/products/search")
async def search_products(q: str = None, category: str = "all", source: str = "all", limit: int = 50):
    """Tìm kiếm sản phẩm chi tiết từ kho dữ liệu đã trích xuất (Gold Layer)"""
    mongo_products = mongo_store.list_products(query_text=q, category=category, source=source, limit=limit)
    if mongo_products:
        return mongo_products

    results = []
    output_dir = project_root / "store" / "outputs"

    if output_dir.exists():
        for f in output_dir.glob("**/*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as j:
                    data = json.load(j)
                    raw_prods = data.get("products", [])
                    src = data.get("source_site", f.parent.name)

                    for p in raw_prods:
                        if source != "all" and src != source:
                            continue
                        name = p.get("name", "")
                        if q and q.lower() not in name.lower():
                            continue
                        p_cat = p.get("category", "Khác")
                        if category != "all" and p_cat != category:
                            continue

                        results.append({
                            "name": name,
                            "price": p.get("price", 0),
                            "original_price": p.get("original_price"),
                            "url": p.get("url"),
                            "source": src,
                            "category": p_cat,
                            "image": p.get("image_url"),
                            "brand": p.get("brand"),
                            "updated_at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
                        })
            except:
                continue

    results.sort(key=lambda x: x["updated_at"], reverse=True)
    return results[:limit]


@app.get("/api/extraction/rules")
async def list_extraction_rules():
    _seed_extraction_rules()
    return rule_summaries(mongo_store.list_rule_structures(), lambda domain, limit: _raw_artifacts(domain, limit))


@app.get("/api/extraction/raw-artifacts")
async def list_raw_artifacts(domain: str | None = None, limit: int = Query(default=80, ge=1, le=500)):
    return _raw_artifacts(domain, limit)


@app.get("/api/extraction/rules/{domain}")
async def get_extraction_rule(domain: str, target: str = "product_detail", raw_artifact_id: str | None = None):
    domain = safe_rule_domain(domain)
    _seed_extraction_rules()
    rule = mongo_store.rule_structure(domain)
    if not rule:
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    structure = rule["structure"]
    targets = targets_for(structure)
    if target not in targets:
        target = targets[0] if targets else target
    raw_page, html = _raw_artifact_html(raw_artifact_id, domain)
    fields = target_fields(structure, target)
    return {
        "domain": structure.get("domain") or domain,
        "target": target,
        "targets": targets,
        "version": rule["version"],
        "fields": fields,
        "raw_artifacts": _raw_artifacts(domain),
        "raw_page": raw_page,
        "preview": field_preview(html, fields)
    }


@app.post("/api/extraction/rules/{domain}/preview")
async def preview_extraction_rule(domain: str, payload: ExtractionPreviewSchema):
    domain = safe_rule_domain(domain)
    _seed_extraction_rules()
    if not mongo_store.rule_structure(domain):
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    raw_page, html = _raw_artifact_html(payload.raw_artifact_id, domain)
    fields = [model_dump(field) for field in payload.fields]
    return {
        "domain": domain,
        "target": payload.target,
        "raw_page": raw_page,
        "preview": field_preview(html, fields)
    }


@app.patch("/api/extraction/rules/{domain}")
async def save_extraction_rule(
    domain: str,
    payload: ExtractionRulePatchSchema,
    role: str = Depends(require_mutation_session),
):
    domain = safe_rule_domain(domain)
    _seed_extraction_rules()
    rule = mongo_store.rule_structure(domain)
    if not rule:
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    structure = rule["structure"]
    if payload.target not in structure or not isinstance(structure[payload.target], dict):
        raise HTTPException(status_code=400, detail="Rule target is missing")
    structure[payload.target]["fields"] = [model_dump(field) for field in payload.fields]
    saved = mongo_store.save_rule_structure(domain, structure, payload.expected_version)
    if saved and saved.get("conflict"):
        raise HTTPException(status_code=409, detail="Extraction rule changed; reload before saving")
    if not saved:
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not save extraction rule")
    version = saved["version"]
    _audit_rule(domain, payload.target, role, version, payload.raw_artifact_id)
    return {"status": "saved", "domain": domain, "target": payload.target, "field_count": len(payload.fields), "version": version}


@app.get("/api/dedup/candidates")
async def get_dedup_candidates(
    status: str | None = Query(default="pending"),
    limit: int = Query(default=20, ge=1, le=100),
):
    if status and status not in {"pending", "merged", "rejected", "needs_review", "all"}:
        raise HTTPException(status_code=400, detail="Invalid dedup queue status")
    rows = list(_dedup_queue()["candidates"].values())
    if status and status != "all":
        rows = [row for row in rows if row.get("status") == status]
    rows.sort(key=lambda row: (row.get("status") != "pending", -row.get("confidence", 0)))
    return rows[:limit]


@app.post("/api/dedup/candidates/{candidate_id}/decision")
async def save_dedup_decision(
    candidate_id: str,
    payload: DedupDecisionSchema,
    role: str = Depends(require_mutation_session),
):
    if payload.status not in {"pending", "merged", "rejected", "needs_review"}:
        raise HTTPException(status_code=400, detail="Invalid dedup queue status")
    queue = _dedup_queue()
    candidate = queue["candidates"].get(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Dedup candidate not found")
    if not mongo_store.update_dedup_candidate(candidate_id, payload.status, payload.note, role):
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not save dedup decision")
    return {"status": "recorded", "candidate_id": candidate_id, "queue_status": payload.status}


@app.get("/api/sources")
async def get_all_sources():
    sources = mongo_store.list_sources()
    result = []
    for s in sources:
        domain = s.get("domain") or urlparse(s.get("url") or "").netloc
        result.append({
            "id": s["id"],
            "name": s.get("name"),
            "url": s.get("url"),
            "type": s.get("type"),
            "category": s.get("category"),
            "group": source_group(s.get("category")),
            "note": s.get("note"),
            "saved_locally": bool(mongo_store.raw_pages(domain, 1)),
        })
    return result


@app.post("/api/sources")
async def create_source(s: SourceSchema, role: str = Depends(require_mutation_session)):
    created = mongo_store.create_source(model_dump(s))
    if not created:
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not create source")
    return created


@app.put("/api/sources/{source_id}")
async def update_source(source_id: str, s: SourceSchema, role: str = Depends(require_mutation_session)):
    db_source = mongo_store.update_source(source_id, model_dump(s))
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str, role: str = Depends(require_mutation_session)):
    if not mongo_store.delete_source(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "deleted"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Admin Center"}


@app.get("/api/ready")
async def ready():
    if not mongo_store.ready():
        raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
    return {"status": "ready", "database": "MongoDB Atlas"}


@app.post("/api/auth/login")
async def login(payload: LoginSchema, request: Request, response: Response):
    key = login_key(request)
    login_rate_limiter.check(key)
    if not verify_password(payload.password):
        login_rate_limiter.record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid admin password")
    login_rate_limiter.record_success(key)
    return create_session(response)


@app.get("/api/auth/session")
async def current_session(request: Request):
    return session_from_request(request)


@app.post("/api/auth/logout")
async def logout(response: Response):
    clear_session(response)
    return {"status": "logged_out"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

