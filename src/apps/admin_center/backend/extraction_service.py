from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from fastapi import HTTPException

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import extraction_writer
from apps.admin_center.backend.gemini_service import analyze_html
from apps.admin_center.backend.gemini_service import extract_records
from apps.admin_center.backend.gemini_service import generate_review_candidates
from apps.admin_center.backend.gemini_service import generate_synthetic_data
from apps.admin_center.backend.pg_store import now_utc
from apps.admin_center.backend.rule_catalog import rule_summaries, target_fields, targets_for
from apps.admin_center.backend.schemas import AIReviewDecisionSchema, AIReviewGenerateSchema, ExtractionPreviewSchema, ExtractionRulePatchSchema, GeminiExtractionAnalyzeSchema, SyntheticBatchDecisionSchema, SyntheticDataGenerateSchema
from apps.admin_center.backend.services import field_preview, json_hash, model_dump, safe_rule_domain


DEFAULT_SYNTHETIC_COLUMNS = [
    "name",
    "category",
    "brand",
    "price",
    "currency",
    "rating",
    "store_name",
    "store_address",
    "source",
    "url",
]
ALLOWED_SYNTHETIC_COLUMNS = {
    "name",
    "product_name",
    "category",
    "brand",
    "price",
    "currency",
    "rating",
    "store_name",
    "store_address",
    "store_url",
    "source",
    "url",
}
SYNTHETIC_REQUIRED_COLUMNS = {"name", "category", "price"}
MAX_SYNTHETIC_LIST_ITEMS = 12


def _synthetic_value(row: dict[str, Any], *names: str) -> Any:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _semantic_validate_synthetic_rows(
    rows: list[dict[str, Any]],
    product_types: list[str],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    allowed_categories = {item.casefold() for item in product_types}
    valid_rows = 0

    for index, row in enumerate(rows, start=1):
        row_errors: list[str] = []
        name = str(_synthetic_value(row, "name", "product_name") or "").strip()
        category = str(_synthetic_value(row, "category") or "").strip()
        store_name = str(_synthetic_value(row, "store_name") or "").strip()
        price = extraction_writer.clean_price(_synthetic_value(row, "price"))
        rating_raw = _synthetic_value(row, "rating")
        url = str(_synthetic_value(row, "url") or "").strip()
        source_url = str(_synthetic_value(row, "source") or "").strip()

        if len(name) < 3 or name.casefold() in {"sản phẩm", "san pham", "product"}:
            row_errors.append("product name is missing or too generic")
        if not category or (allowed_categories and category.casefold() not in allowed_categories):
            row_errors.append("category is outside requested product types")
        if price is None or price <= 0:
            row_errors.append("price must be a positive number")
        elif price > 10_000_000_000:
            row_errors.append("price exceeds the supported range")
        if rating_raw not in (None, ""):
            try:
                rating = float(str(rating_raw).replace(",", "."))
                if not 4.0 <= rating <= 5.0:
                    row_errors.append("rating must be between 4.0 and 5.0")
            except (TypeError, ValueError):
                row_errors.append("rating must be numeric")
        for field_name, candidate_url in (("url", url), ("source", source_url)):
            if candidate_url:
                parsed = urlparse(candidate_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    row_errors.append(f"{field_name} must be an absolute HTTP URL")
        identity = (name.casefold(), category.casefold(), store_name.casefold())
        if identity in seen:
            row_errors.append("duplicate product row")
        seen.add(identity)

        if row_errors:
            errors.append({"row": index, "reasons": row_errors})
        else:
            valid_rows += 1

    return {
        "accepted": not errors and valid_rows == len(rows),
        "status": "validated" if not errors and valid_rows == len(rows) else "rejected",
        "valid_rows": valid_rows,
        "invalid_rows": len(rows) - valid_rows,
        "errors": errors,
    }


def _grounding_evidence(source: dict[str, Any]) -> list[str]:
    domain = str(source.get("domain") or urlparse(str(source.get("url") or "")).netloc).removeprefix("www.")
    evidence = []
    for artifact in deps.raw_artifacts(domain, 3):
        raw_page, html = deps.raw_artifact_html(artifact.get("id"), domain)
        if not html:
            continue
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()[:1800]
        if text:
            evidence.append(f"URL: {(raw_page or artifact).get('url') or ''}\nNội dung: {text}")
    return evidence


def _validate_synthetic_request(
    columns: list[str],
    product_types: list[str],
    reference_sources: list[str],
) -> None:
    if len(columns) > 20 or any(column not in ALLOWED_SYNTHETIC_COLUMNS for column in columns):
        raise HTTPException(status_code=422, detail="Synthetic output columns contain unsupported values")
    normalized_columns = {"name" if column == "product_name" else column for column in columns}
    if not SYNTHETIC_REQUIRED_COLUMNS.issubset(normalized_columns):
        raise HTTPException(status_code=422, detail="Synthetic output must include name, category, and price")
    if len(product_types) > MAX_SYNTHETIC_LIST_ITEMS or any(len(item) > 120 for item in product_types):
        raise HTTPException(status_code=422, detail="Too many or overly long product types")
    if len(reference_sources) > MAX_SYNTHETIC_LIST_ITEMS or any(len(item) > 500 for item in reference_sources):
        raise HTTPException(status_code=422, detail="Too many or overly long reference sources")


def list_rules() -> list[dict]:
    deps.seed_extraction_rules()
    return rule_summaries(deps.data_store.list_rule_structures(), lambda domain, limit: deps.raw_artifacts(domain, limit))


def raw_artifact_detail(artifact_id: str, domain: str | None = None) -> dict:
    raw_page, html = deps.raw_artifact_html(artifact_id, domain)
    if not raw_page:
        raise HTTPException(status_code=404, detail="Raw artifact not found")
    html = html or ""
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True) if html else ""
    return {
        "raw_page": raw_page,
        "html_excerpt": html[:4000],
        "text_preview": text[:1200],
        "content_length": len(html),
    }


def rule_detail(domain: str, target: str = "product_detail", raw_artifact_id: str | None = None) -> dict:
    domain = safe_rule_domain(domain)
    deps.seed_extraction_rules()
    rule = deps.data_store.rule_structure(domain)
    if not rule:
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    structure = rule["structure"]
    targets = targets_for(structure)
    if target not in targets:
        target = targets[0] if targets else target
    raw_page, html = deps.raw_artifact_html(raw_artifact_id, domain)
    fields = target_fields(structure, target)
    return {
        "domain": structure.get("domain") or domain,
        "target": target,
        "targets": targets,
        "version": rule["version"],
        "fields": fields,
        "raw_artifacts": deps.raw_artifacts(domain),
        "raw_page": raw_page,
        "preview": field_preview(html, fields),
    }


def preview_rule(domain: str, payload: ExtractionPreviewSchema) -> dict:
    domain = safe_rule_domain(domain)
    deps.seed_extraction_rules()
    if not deps.data_store.rule_structure(domain):
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    raw_page, html = deps.raw_artifact_html(payload.raw_artifact_id, domain)
    fields = [model_dump(field) for field in payload.fields]
    return {
        "domain": domain,
        "target": payload.target,
        "raw_page": raw_page,
        "preview": field_preview(html, fields),
    }


def save_rule(domain: str, payload: ExtractionRulePatchSchema, role: str) -> dict:
    domain = safe_rule_domain(domain)
    deps.seed_extraction_rules()
    rule = deps.data_store.rule_structure(domain)
    if not rule:
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    structure = rule["structure"]
    if payload.target not in structure or not isinstance(structure[payload.target], dict):
        raise HTTPException(status_code=400, detail="Rule target is missing")
    structure[payload.target]["fields"] = [model_dump(field) for field in payload.fields]
    saved = deps.data_store.save_rule_structure(domain, structure, payload.expected_version)
    if saved and saved.get("conflict"):
        raise HTTPException(status_code=409, detail="Extraction rule changed; reload before saving")
    if not saved:
        raise HTTPException(status_code=503, detail="PostgreSQL could not save extraction rule")
    version = saved["version"]
    deps.audit_rule(domain, payload.target, role, version, payload.raw_artifact_id)
    return {"status": "saved", "domain": domain, "target": payload.target, "field_count": len(payload.fields), "version": version}


def rollback_rule(domain: str, version: str | None, role: str) -> dict:
    domain = safe_rule_domain(domain)
    restored = deps.data_store.rollback_rule(domain, version)
    if not restored:
        raise HTTPException(status_code=404, detail="Previous extraction rule version not found")
    deps.data_store.record_rule_event({
        "event": "rule_rollback",
        "domain": domain,
        "version": restored.get("version"),
        "role": role,
        "created_at": now_utc(),
    })
    return {"status": "rolled_back", **restored}


def list_rule_candidates(domain: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
    return deps.data_store.list_rule_candidates(domain, status, limit)


def promote_rule_candidate(candidate_id: str, role: str, expected_version: str | None = None) -> dict:
    promoted = deps.data_store.promote_rule_candidate(candidate_id, expected_version)
    if not promoted:
        raise HTTPException(status_code=404, detail="Validated rule candidate not found")
    if promoted.get("conflict"):
        raise HTTPException(status_code=409, detail="Extraction rule changed; reload before promoting")
    if not promoted.get("promoted"):
        raise HTTPException(status_code=400, detail=promoted.get("reason") or "Rule candidate was not promoted")
    deps.data_store.record_rule_event({
        "event": "rule_candidate_promote",
        "domain": promoted.get("domain"),
        "version": promoted.get("version"),
        "role": role,
        "candidate_id": candidate_id,
        "created_at": now_utc(),
    })
    return {"status": "promoted", **promoted}


def analyze_with_gemini(payload: GeminiExtractionAnalyzeSchema) -> dict:
    domain = safe_rule_domain(payload.domain)
    html = payload.html
    raw_page = None
    if not html and payload.raw_artifact_id:
        raw_page, html = deps.raw_artifact_html(payload.raw_artifact_id, domain)
    if not html:
        raise HTTPException(status_code=400, detail="HTML content is required for Gemini analysis")

    try:
        result = analyze_html(
            domain=domain,
            html=html,
            url=payload.url or (raw_page or {}).get("url"),
            page_type=payload.page_type or (raw_page or {}).get("page_type"),
            target_hint=payload.target_hint,
        )
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini returned invalid JSON: {exc}") from exc
    return {
        "domain": domain,
        "model": result.model,
        "prompt": result.prompt,
        "draft": result.draft,
        "validation": result.validation,
        "raw_page": raw_page,
    }


def extract_records_with_gemini(payload: GeminiExtractionAnalyzeSchema) -> dict:
    domain = safe_rule_domain(payload.domain)
    html = payload.html
    raw_page = None
    if not html and payload.raw_artifact_id:
        raw_page, html = deps.raw_artifact_html(payload.raw_artifact_id, domain)
    if not html:
        raise HTTPException(status_code=400, detail="HTML content is required for Gemini extraction")

    try:
        result = extract_records(
            domain=domain,
            html=html,
            url=payload.url or (raw_page or {}).get("url"),
            page_type=payload.page_type or (raw_page or {}).get("page_type"),
            target_hint=payload.target_hint,
        )
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini returned invalid JSON: {exc}") from exc
    return {
        "domain": domain,
        "model": result.model,
        "prompt": result.prompt,
        "records": result.records,
        "raw_page": raw_page,
    }


def generate_ai_review_list(payload: AIReviewGenerateSchema) -> dict:
    domain = safe_rule_domain(payload.domain)
    html = payload.html
    raw_page = None
    if not html and payload.raw_artifact_id:
        raw_page, html = deps.raw_artifact_html(payload.raw_artifact_id, domain)
    if not html:
        raise HTTPException(status_code=400, detail="HTML content is required for AI review generation")

    try:
        result = generate_review_candidates(
            domain=domain,
            html=html,
            url=payload.url or (raw_page or {}).get("url"),
            page_type=payload.page_type or (raw_page or {}).get("page_type"),
            target_hint=payload.target_hint,
            max_items=payload.max_items,
        )
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini returned invalid JSON: {exc}") from exc

    items = []
    for index, item in enumerate(result.candidates.get("items") or [], start=1):
        candidate = dict(item)
        candidate_type = candidate.get("entity_type") or "product"
        candidate_payload = {
            "name": candidate.get("name"),
            "url": candidate.get("url"),
            "price": candidate.get("price"),
            "currency": candidate.get("currency"),
            "store_name": candidate.get("store_name"),
            "store_url": candidate.get("store_url"),
            "store_address": candidate.get("address"),
            "store_phone": candidate.get("phone"),
            "image_url": candidate.get("image_url"),
            "confidence": candidate.get("confidence"),
            "reason": candidate.get("reason"),
        }
        review_item = {
            "review_id": json_hash({
                "domain": domain,
                "raw_page_id": (raw_page or {}).get("id") or payload.raw_artifact_id or "",
                "entity_type": candidate_type,
                "index": index,
                "name": candidate.get("name"),
                "url": candidate.get("url"),
            }),
            "domain": domain,
            "source_id": None,
            "raw_page_id": (raw_page or {}).get("id") or payload.raw_artifact_id,
            "raw_page_url": (raw_page or {}).get("url") or payload.url,
            "page_type": payload.page_type or (raw_page or {}).get("page_type"),
            "entity_type": candidate_type,
            "payload": candidate_payload,
            "confidence": candidate.get("confidence") or 0.0,
            "reason": candidate.get("reason") or "",
            "status": candidate.get("review_status") or "needs_review",
            "note": "",
            "model": result.model,
        }
        items.append(review_item)

    deps.data_store.sync_ai_review_candidates(items)
    return {
        "domain": domain,
        "model": result.model,
        "prompt": result.prompt,
        "raw_page": raw_page,
        "review_items": items,
        "summary": {
            "total": len(items),
            "needs_review": sum(1 for item in items if item.get("status") == "needs_review"),
        },
    }


def generate_source_synthetic_data(source_id: str, payload: SyntheticDataGenerateSchema) -> dict:
    source = next((row for row in deps.data_store.list_sources() if str(row.get("id")) == str(source_id)), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    columns = _normalize_columns(payload.output_columns)
    product_types = [item for item in _clean_list(payload.product_types) if item]
    if not product_types:
        product_types = _clean_list([source.get("category") or "hàng tiêu dùng"])
    reference_sources = _clean_list(payload.reference_sources)
    if not reference_sources:
        reference_sources = [value for value in [source.get("url"), source.get("name")] if value]
    region = (payload.region or "Toàn quốc").strip() or "Toàn quốc"
    _validate_synthetic_request(columns, product_types, reference_sources)
    evidence_summaries = _grounding_evidence(source) if payload.generation_mode == "grounded_synthetic" else []
    if payload.generation_mode == "grounded_synthetic" and not evidence_summaries:
        raise HTTPException(status_code=400, detail="Grounded synthetic generation requires captured raw-page evidence")

    try:
        result = generate_synthetic_data(
            row_count=payload.row_count,
            product_types=product_types,
            reference_sources=reference_sources,
            region=region,
            output_columns=columns,
            generation_mode=payload.generation_mode,
            evidence_summaries=evidence_summaries,
        )
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini returned invalid synthetic data: {exc}") from exc

    rows = result.rows
    validation = _semantic_validate_synthetic_rows(rows, product_types)
    persisted = None
    if payload.persist:
        db = deps.data_store.get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="PostgreSQL is unavailable")
        batch_id = f"synthetic-{json_hash({'source_id': source_id, 'mode': payload.generation_mode, 'columns': columns, 'rows': rows})}"
        docs = []
        target_collection = db.sc_synthetic_products if validation["accepted"] else db.sc_synthetic_quarantine
        for index, row in enumerate(rows, start=1):
            docs.append({
                "synthetic_id": f"{batch_id}-{index}",
                "batch_id": batch_id,
                "source_id": source_id,
                "source_domain": source.get("domain") or urlparse(str(source.get("url") or "")).netloc,
                "source_name": source.get("name"),
                "payload": row,
                "data_origin": payload.generation_mode,
                "validation_status": validation["status"],
                "review_status": "validated" if validation["accepted"] else "rejected",
                "validation": validation,
                "model": result.model,
                "prompt_hash": json_hash({"prompt": result.prompt}),
                "updated_at": now_utc(),
            })
        if docs:
            for doc in docs:
                target_collection.update_one(
                    {"synthetic_id": doc["synthetic_id"]},
                    {"$set": doc, "$setOnInsert": {"created_at": now_utc()}},
                    upsert=True,
                )
        persisted = {
            "collection": "sc_synthetic_products" if validation["accepted"] else "sc_synthetic_quarantine",
            "batch_id": batch_id,
            "rows": len(docs),
            "review_status": "validated" if validation["accepted"] else "rejected",
        }

    return {
        "source_id": source_id,
        "source": source,
        "model": result.model,
        "prompt": result.prompt,
        "data_origin": payload.generation_mode,
        "columns": columns,
        "rows": rows,
        "markdown": _rows_to_markdown(rows, columns),
        "csv": _rows_to_csv(rows, columns),
        "persisted": persisted,
        "validation": validation,
        "lifecycle": ["draft", validation["status"]],
        "summary": {
            "total": len(rows),
            "product_types": product_types,
            "reference_sources": reference_sources,
            "region": region,
            "evidence_count": len(evidence_summaries),
        },
    }


def list_synthetic_batches(
    source_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    def timestamp(value: Any) -> float:
        if not isinstance(value, datetime):
            return 0.0
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    db = deps.data_store.get_db()
    if db is None:
        return []
    query: dict[str, Any] = {}
    if source_id:
        query["source_id"] = source_id
    if status:
        query["review_status"] = status
    batches: dict[str, dict[str, Any]] = {}
    for collection_name in ("sc_synthetic_products", "sc_synthetic_quarantine"):
        collection = getattr(db, collection_name)
        docs = collection.find(query, {"_id": False}).sort([("updated_at", -1)]).limit(max(1, min(limit * 200, 20000)))
        for doc in docs:
            batch_id = str(doc.get("batch_id") or "")
            if not batch_id:
                continue
            current = batches.setdefault(batch_id, {
                "id": batch_id,
                "batch_id": batch_id,
                "source_id": doc.get("source_id"),
                "source_name": doc.get("source_name"),
                "source_domain": doc.get("source_domain"),
                "data_origin": doc.get("data_origin"),
                "validation_status": doc.get("validation_status"),
                "review_status": doc.get("review_status"),
                "model": doc.get("model"),
                "collection": collection_name,
                "rows": 0,
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "reviewed_at": doc.get("reviewed_at"),
                "reviewed_by": doc.get("reviewed_by"),
                "review_note": doc.get("review_note"),
            })
            current["rows"] += 1
            for field in ("updated_at", "reviewed_at"):
                candidate = doc.get(field)
                if candidate and timestamp(candidate) > timestamp(current.get(field)):
                    current[field] = candidate
                    if field == "updated_at":
                        current["review_status"] = doc.get("review_status")
    ordered = sorted(
        batches.values(),
        key=lambda item: timestamp(item.get("updated_at") or item.get("created_at")),
        reverse=True,
    )
    return ordered[:max(1, min(limit, 500))]


def update_synthetic_batch_decision(
    source_id: str,
    batch_id: str,
    payload: SyntheticBatchDecisionSchema,
    role: str,
) -> dict:
    db = deps.data_store.get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="PostgreSQL is unavailable")
    existing = db.sc_synthetic_products.find_one(
        {"source_id": source_id, "batch_id": batch_id, "review_status": {"$in": ["validated", "approved", "rejected"]}},
        {"_id": False, "batch_id": True},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Validated synthetic batch not found")
    decided_at = now_utc()
    result = db.sc_synthetic_products.update_many(
        {"source_id": source_id, "batch_id": batch_id},
        {"$set": {
            "review_status": payload.status,
            "review_note": payload.note,
            "reviewed_by": role,
            "reviewed_at": decided_at,
            "updated_at": decided_at,
        }},
    )
    return {
        "status": payload.status,
        "batch_id": batch_id,
        "rows": int(result.modified_count),
    }


def _clean_list(values: list[Any]) -> list[str]:
    return [str(value or "").strip() for value in values if str(value or "").strip()]


def _normalize_columns(columns: list[str]) -> list[str]:
    cleaned = [item.lower() for item in _clean_list(columns)]
    return list(dict.fromkeys(cleaned or DEFAULT_SYNTHETIC_COLUMNS))


def _rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return output.getvalue()


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")


def _rows_to_markdown(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "| " + " | ".join(_markdown_cell(column) for column in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(_markdown_cell(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def _synthetic_row_to_record(row: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    lower = {str(key).strip().lower(): value for key, value in row.items()}

    def pick(*names: str) -> Any:
        for name in names:
            key = name.lower()
            if lower.get(key) not in (None, ""):
                return lower[key]
        return None

    return {
        "entity_type": "product",
        "name": pick("name", "product_name", "ten_san_pham", "tên sản phẩm", "san_pham", "sản phẩm"),
        "price": pick("price", "price_numeric", "gia", "giá"),
        "currency": pick("currency", "don_vi_tien", "đơn vị tiền") or "VND",
        "category": pick("category", "loai_san_pham", "loại sản phẩm", "danh_muc", "danh mục") or source.get("category"),
        "brand": pick("brand", "thuong_hieu", "thương hiệu"),
        "store_name": pick("store_name", "kenh_ban", "kênh bán", "cua_hang", "cửa hàng") or source.get("name"),
        "store_address": pick("store_address", "address", "dia_chi", "địa chỉ"),
        "store_url": pick("store_url") or source.get("url"),
        "url": pick("url", "source", "nguon", "nguồn") or source.get("url"),
        "rating": pick("rating", "danh_gia", "đánh giá"),
        "source": pick("source", "nguon", "nguồn") or source.get("url") or source.get("name"),
        "raw_data": row,
    }


def list_ai_review_list(status: str | None = "needs_review", domain: str | None = None, limit: int = 50) -> list[dict]:
    return deps.data_store.list_ai_review_candidates(status, domain, limit)


def update_ai_review_decision(review_id: str, payload: AIReviewDecisionSchema, role: str) -> dict:
    candidate = deps.data_store.ai_review_candidate(review_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="AI review candidate not found")
    if not deps.data_store.update_ai_review_candidate(review_id, payload.status, payload.note, role):
        raise HTTPException(status_code=503, detail="PostgreSQL could not save AI review decision")
    return {"status": "recorded", "review_id": review_id, "queue_status": payload.status}


def publish_ai_review_candidate(review_id: str, role: str) -> dict:
    candidate = deps.data_store.ai_review_candidate(review_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="AI review candidate not found")
    payload = candidate.get("payload") or {}
    entity_type = str(candidate.get("entity_type") or "product").lower()
    raw_page_id = candidate.get("raw_page_id")
    domain = candidate.get("domain") or ""
    if entity_type == "store":
        raise HTTPException(status_code=400, detail="Store-only candidates are no longer published separately; attach store fields to product records.")
    product = extraction_writer.product_payload(payload, domain=domain, url=candidate.get("raw_page_url"), raw_page_id=raw_page_id, source_id=candidate.get("source_id"))
    if not product:
        raise HTTPException(status_code=400, detail="AI review candidate does not contain a valid product payload")
    product.update({
        "data_origin": "ai_extracted",
        "evidence_id": raw_page_id,
        "extraction_method": "ai_review",
        "model": candidate.get("model"),
        "validation_score": candidate.get("confidence"),
    })
    db = deps.data_store.get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="PostgreSQL is unavailable")
    db.sc_products.update_one(
        {"product_id": product["product_id"]},
        {
            "$set": product,
            "$unset": {"store_id": "", "raw_data.store_id": ""},
            "$setOnInsert": {"created_at": now_utc()},
        },
        upsert=True,
    )
    offer = extraction_writer.offer_payload(product)
    if offer:
        db.sc_offers.update_one(
            {"offer_id": offer["offer_id"]},
            {"$set": offer, "$unset": {"store_id": ""}, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True,
        )
    observation = extraction_writer.price_observation_payload(product)
    if observation:
        db.sc_price_observations.update_one(
            {"observation_id": observation["observation_id"]},
            {"$set": observation, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True,
        )
    deps.data_store.update_ai_review_candidate(review_id, "approved", candidate.get("note"), role)
    return {"status": "published", "review_id": review_id, "entity_type": entity_type}

