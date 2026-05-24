from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

# Keep the package import root available for local uvicorn runs.
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))

from apps.admin_center.backend.mhtml_processor import MHTMLProcessor
from apps.admin_center.backend.mongo_store import AdminMongoStore
from apps.admin_center.backend.rule_catalog import seed_structures
from apps.admin_center.backend.services import dedup_candidate_id, normalize_product_name

mongo_store = AdminMongoStore()
structures_dir = Path(__file__).resolve().parent / "structures"
admin_store_dir = project_root / "store" / "admin"
dedup_queue_path = admin_store_dir / "dedup_queue.json"


def require_mongo_ready() -> None:
    if not mongo_store.ready():
        raise HTTPException(status_code=503, detail="MongoDB Atlas is not ready for Admin Center mutations")


def require_admin_session(request: Request) -> str:
    return "internal"


def require_mutation_session(request: Request) -> str:
    require_mongo_ready()
    return "internal"


def read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def raw_dirs(domain: str | None = None) -> list[Path]:
    raw_dir = project_root / "store" / "raw"
    if not domain:
        return [raw_dir] if raw_dir.exists() else []
    aliases = {domain, domain.removeprefix("www.")}
    if not domain.startswith("www."):
        aliases.add(f"www.{domain}")
    return [raw_dir / alias for alias in aliases if (raw_dir / alias).exists()]


def artifact_id(path: Path) -> str:
    relative = path.relative_to(project_root).as_posix()
    return hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16]


def meta_for_raw(path: Path) -> dict[str, Any]:
    meta_path = Path(f"{path}.meta.json")
    if meta_path.exists():
        try:
            return read_json(meta_path)
        except Exception:
            return {}
    return {}


def raw_artifact_record(path: Path) -> dict[str, Any]:
    meta = meta_for_raw(path)
    return {
        "id": artifact_id(path),
        "filename": path.name,
        "path": str(path.relative_to(project_root)),
        "domain": path.parent.name,
        "task_id": path.name,
        "url": meta.get("url"),
        "page_type": meta.get("page_type", "unknown"),
        "size": path.stat().st_size,
        "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
    }


def raw_artifacts(domain: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
    mongo_artifacts = mongo_store.raw_pages(domain, limit)
    if mongo_artifacts:
        return mongo_artifacts

    files = []
    for root in raw_dirs(domain):
        files.extend(root.glob("**/*.mhtml"))
    files.sort(key=os.path.getmtime, reverse=True)
    return [raw_artifact_record(path) for path in files[:limit]]


def raw_artifact_path(artifact_id_value: str | None, domain: str | None = None) -> Path | None:
    if not artifact_id_value:
        artifacts = raw_artifacts(domain, limit=1)
        return project_root / artifacts[0]["path"] if artifacts else None
    for artifact in raw_artifacts(domain, limit=500):
        if artifact["id"] == artifact_id_value:
            return project_root / artifact["path"]
    raise HTTPException(status_code=404, detail="Raw artifact not found")


def raw_artifact_html(artifact_id_value: str | None, domain: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    raw_doc = mongo_store.raw_page(artifact_id_value, domain)
    if raw_doc:
        return mongo_store._raw_page_view(raw_doc), mongo_store.raw_page_html(raw_doc)
    raw_file = raw_artifact_path(artifact_id_value, domain)
    if raw_file is None:
        return None, None
    return raw_artifact_record(raw_file), MHTMLProcessor.decode_file(raw_file)


def load_output_products(limit: int = 600) -> list[dict[str, Any]]:
    products = mongo_store.list_products(limit=limit)
    if products:
        return products

    products = []
    output_dir = project_root / "store" / "outputs"
    if not output_dir.exists():
        return products

    for path in sorted(output_dir.glob("**/*.json"), key=os.path.getmtime, reverse=True):
        try:
            data = read_json(path)
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
                "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
            })
            if len(products) >= limit:
                return products
    return products


def dedup_candidates(limit: int) -> list[dict[str, Any]]:
    products = load_output_products()
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
                "right": right,
            })
    candidates.sort(key=lambda row: row["confidence"], reverse=True)
    return candidates[:limit]


def refresh_dedup_queue() -> dict[str, Any]:
    """Recompute dedup candidates on demand.

    The GET endpoint only reads the existing queue; this function does the
    expensive pairwise product comparison when the user explicitly clicks refresh.
    """
    candidates = dedup_candidates(200)
    mongo_store.sync_dedup_candidates(candidates)
    rows = mongo_store.list_dedup_candidates("all", 500)
    if rows:
        return {"candidates": {row["id"]: row for row in rows}}
    queue = read_json(dedup_queue_path) if dedup_queue_path.exists() else {"candidates": {}}
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
    write_json(dedup_queue_path, queue)
    return dedup_queue()


def dedup_queue() -> dict[str, Any]:
    """Read the current dedup queue without recomputing candidate pairs."""
    rows = mongo_store.list_dedup_candidates("all", 500)
    if rows:
        return {"candidates": {row["id"]: row for row in rows}}
    queue = read_json(dedup_queue_path) if dedup_queue_path.exists() else {"candidates": {}}
    queue.setdefault("candidates", {})
    return queue


def audit_rule(domain: str, target: str, role: str, version: str, artifact_id_value: str | None) -> None:
    event = {
        "event": "rule_patch",
        "domain": domain,
        "target": target,
        "role": role,
        "version": version,
        "raw_artifact_id": artifact_id_value,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    mongo_store.record_rule_event(event)


def seed_extraction_rules() -> None:
    mongo_store.seed_rule_structures(seed_structures(structures_dir))


def price_history_months(lookback_days: int = 400) -> list[dict[str, Any]]:
    return mongo_store.price_history_months(lookback_days)


def market_stats() -> dict[str, Any]:
    return mongo_store.market_stats()
