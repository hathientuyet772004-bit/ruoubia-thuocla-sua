from __future__ import annotations

import csv
import io
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
from apps.admin_center.backend.mongo_store import now_utc
from apps.admin_center.backend.rule_catalog import rule_summaries, target_fields, targets_for
from apps.admin_center.backend.schemas import AIReviewDecisionSchema, AIReviewGenerateSchema, ExtractionPreviewSchema, ExtractionRulePatchSchema, GeminiExtractionAnalyzeSchema, SyntheticDataGenerateSchema
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


def list_rules() -> list[dict]:
    deps.seed_extraction_rules()
    return rule_summaries(deps.mongo_store.list_rule_structures(), lambda domain, limit: deps.raw_artifacts(domain, limit))


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
    rule = deps.mongo_store.rule_structure(domain)
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
    if not deps.mongo_store.rule_structure(domain):
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
    rule = deps.mongo_store.rule_structure(domain)
    if not rule:
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    structure = rule["structure"]
    if payload.target not in structure or not isinstance(structure[payload.target], dict):
        raise HTTPException(status_code=400, detail="Rule target is missing")
    structure[payload.target]["fields"] = [model_dump(field) for field in payload.fields]
    saved = deps.mongo_store.save_rule_structure(domain, structure, payload.expected_version)
    if saved and saved.get("conflict"):
        raise HTTPException(status_code=409, detail="Extraction rule changed; reload before saving")
    if not saved:
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not save extraction rule")
    version = saved["version"]
    deps.audit_rule(domain, payload.target, role, version, payload.raw_artifact_id)
    return {"status": "saved", "domain": domain, "target": payload.target, "field_count": len(payload.fields), "version": version}


def rollback_rule(domain: str, version: str | None, role: str) -> dict:
    domain = safe_rule_domain(domain)
    restored = deps.mongo_store.rollback_rule(domain, version)
    if not restored:
        raise HTTPException(status_code=404, detail="Previous extraction rule version not found")
    deps.mongo_store.record_rule_event({
        "event": "rule_rollback",
        "domain": domain,
        "version": restored.get("version"),
        "role": role,
        "created_at": now_utc(),
    })
    return {"status": "rolled_back", **restored}


def list_rule_candidates(domain: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
    return deps.mongo_store.list_rule_candidates(domain, status, limit)


def promote_rule_candidate(candidate_id: str, role: str, expected_version: str | None = None) -> dict:
    promoted = deps.mongo_store.promote_rule_candidate(candidate_id, expected_version)
    if not promoted:
        raise HTTPException(status_code=404, detail="Validated rule candidate not found")
    if promoted.get("conflict"):
        raise HTTPException(status_code=409, detail="Extraction rule changed; reload before promoting")
    if not promoted.get("promoted"):
        raise HTTPException(status_code=400, detail=promoted.get("reason") or "Rule candidate was not promoted")
    deps.mongo_store.record_rule_event({
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

    deps.mongo_store.sync_ai_review_candidates(items)
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
    source = next((row for row in deps.mongo_store.list_sources() if str(row.get("id")) == str(source_id)), None)
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

    try:
        result = generate_synthetic_data(
            row_count=payload.row_count,
            product_types=product_types,
            reference_sources=reference_sources,
            region=region,
            output_columns=columns,
        )
    except RuntimeError as exc:
        message = str(exc)
        status_code = 503 if "not configured" in message.lower() else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini returned invalid synthetic data: {exc}") from exc

    rows = result.rows
    persisted = None
    if payload.persist:
        db = deps.mongo_store.get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
        batch_id = f"synthetic-{json_hash({'source_id': source_id, 'row_count': payload.row_count, 'columns': columns, 'rows': rows})}"
        docs = []
        for index, row in enumerate(rows, start=1):
            docs.append({
                "synthetic_id": f"{batch_id}-{index}",
                "batch_id": batch_id,
                "source_id": source_id,
                "source": source,
                "payload": row,
                "data_origin": "synthetic",
                "model": result.model,
                "prompt_hash": json_hash({"prompt": result.prompt}),
                "created_at": now_utc(),
            })
        if docs:
            db.sc_synthetic_products.insert_many(docs)
        persisted = {"collection": "sc_synthetic_products", "batch_id": batch_id, "rows": len(docs)}

    return {
        "source_id": source_id,
        "source": source,
        "model": result.model,
        "prompt": result.prompt,
        "columns": columns,
        "rows": rows,
        "markdown": _rows_to_markdown(rows, columns),
        "csv": _rows_to_csv(rows, columns),
        "persisted": persisted,
        "summary": {
            "total": len(rows),
            "product_types": product_types,
            "reference_sources": reference_sources,
            "region": region,
        },
    }


def _clean_list(values: list[Any]) -> list[str]:
    return [str(value or "").strip() for value in values if str(value or "").strip()]


def _normalize_columns(columns: list[str]) -> list[str]:
    cleaned = _clean_list(columns)
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
    return deps.mongo_store.list_ai_review_candidates(status, domain, limit)


def update_ai_review_decision(review_id: str, payload: AIReviewDecisionSchema, role: str) -> dict:
    candidate = deps.mongo_store.ai_review_candidate(review_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="AI review candidate not found")
    if not deps.mongo_store.update_ai_review_candidate(review_id, payload.status, payload.note, role):
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not save AI review decision")
    return {"status": "recorded", "review_id": review_id, "queue_status": payload.status}


def publish_ai_review_candidate(review_id: str, role: str) -> dict:
    candidate = deps.mongo_store.ai_review_candidate(review_id)
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
    db = deps.mongo_store.get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
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
    deps.mongo_store.update_ai_review_candidate(review_id, "approved", candidate.get("note"), role)
    return {"status": "published", "review_id": review_id, "entity_type": entity_type}
