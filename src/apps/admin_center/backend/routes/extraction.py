from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.admin_center.backend.dependencies import audit_rule, mongo_store, raw_artifact_html, raw_artifacts, require_mutation_session, seed_extraction_rules
from apps.admin_center.backend.rule_catalog import rule_summaries, target_fields, targets_for
from apps.admin_center.backend.schemas import ExtractionPreviewSchema, ExtractionRulePatchSchema
from apps.admin_center.backend.services import field_preview, model_dump, safe_rule_domain

router = APIRouter(prefix="/api/extraction", tags=["extraction"])


@router.get("/rules")
async def list_extraction_rules():
    seed_extraction_rules()
    return rule_summaries(mongo_store.list_rule_structures(), lambda domain, limit: raw_artifacts(domain, limit))


@router.get("/raw-artifacts")
async def list_raw_artifacts(domain: str | None = None, limit: int = Query(default=80, ge=1, le=500)):
    return raw_artifacts(domain, limit)


@router.get("/rules/{domain}")
async def get_extraction_rule(domain: str, target: str = "product_detail", raw_artifact_id: str | None = None):
    domain = safe_rule_domain(domain)
    seed_extraction_rules()
    rule = mongo_store.rule_structure(domain)
    if not rule:
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    structure = rule["structure"]
    targets = targets_for(structure)
    if target not in targets:
        target = targets[0] if targets else target
    raw_page, html = raw_artifact_html(raw_artifact_id, domain)
    fields = target_fields(structure, target)
    return {
        "domain": structure.get("domain") or domain,
        "target": target,
        "targets": targets,
        "version": rule["version"],
        "fields": fields,
        "raw_artifacts": raw_artifacts(domain),
        "raw_page": raw_page,
        "preview": field_preview(html, fields),
    }


@router.post("/rules/{domain}/preview")
async def preview_extraction_rule(domain: str, payload: ExtractionPreviewSchema):
    domain = safe_rule_domain(domain)
    seed_extraction_rules()
    if not mongo_store.rule_structure(domain):
        raise HTTPException(status_code=404, detail="Extraction rule not found")

    raw_page, html = raw_artifact_html(payload.raw_artifact_id, domain)
    fields = [model_dump(field) for field in payload.fields]
    return {
        "domain": domain,
        "target": payload.target,
        "raw_page": raw_page,
        "preview": field_preview(html, fields),
    }


@router.patch("/rules/{domain}")
async def save_extraction_rule(
    domain: str,
    payload: ExtractionRulePatchSchema,
    role: str = Depends(require_mutation_session),
):
    domain = safe_rule_domain(domain)
    seed_extraction_rules()
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
    audit_rule(domain, payload.target, role, version, payload.raw_artifact_id)
    return {"status": "saved", "domain": domain, "target": payload.target, "field_count": len(payload.fields), "version": version}
