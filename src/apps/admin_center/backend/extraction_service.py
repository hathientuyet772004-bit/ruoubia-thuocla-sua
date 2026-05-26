from __future__ import annotations

from bs4 import BeautifulSoup
from fastapi import HTTPException

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import extraction_writer
from apps.admin_center.backend.gemini_service import analyze_html
from apps.admin_center.backend.gemini_service import extract_records
from apps.admin_center.backend.gemini_service import generate_review_candidates
from apps.admin_center.backend.mongo_store import now_utc
from apps.admin_center.backend.rule_catalog import rule_summaries, target_fields, targets_for
from apps.admin_center.backend.schemas import AIReviewDecisionSchema, AIReviewGenerateSchema, ExtractionPreviewSchema, ExtractionRulePatchSchema, GeminiExtractionAnalyzeSchema
from apps.admin_center.backend.services import field_preview, json_hash, model_dump, safe_rule_domain


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
        store = extraction_writer.store_payload(payload, domain=domain, url=candidate.get("raw_page_url"), raw_page_id=raw_page_id, source_id=candidate.get("source_id"))
        if not store:
            raise HTTPException(status_code=400, detail="AI review candidate does not contain a valid store payload")
        db = deps.mongo_store.get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
        db.sc_stores.update_one({"store_id": store["store_id"]}, {"$set": store, "$setOnInsert": {"created_at": now_utc()}}, upsert=True)
    else:
        product = extraction_writer.product_payload(payload, domain=domain, url=candidate.get("raw_page_url"), raw_page_id=raw_page_id, source_id=candidate.get("source_id"))
        if not product:
            raise HTTPException(status_code=400, detail="AI review candidate does not contain a valid product payload")
        db = deps.mongo_store.get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="MongoDB Atlas is unavailable")
        db.sc_products.update_one({"product_id": product["product_id"]}, {"$set": product, "$setOnInsert": {"created_at": now_utc()}}, upsert=True)
        offer = extraction_writer.offer_payload(product)
        if offer:
            db.sc_offers.update_one({"offer_id": offer["offer_id"]}, {"$set": offer, "$setOnInsert": {"created_at": now_utc()}}, upsert=True)
    deps.mongo_store.update_ai_review_candidate(review_id, "approved", candidate.get("note"), role)
    return {"status": "published", "review_id": review_id, "entity_type": entity_type}
