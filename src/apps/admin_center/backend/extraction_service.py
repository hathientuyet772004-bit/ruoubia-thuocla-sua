from __future__ import annotations

from bs4 import BeautifulSoup
from fastapi import HTTPException

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.rule_catalog import rule_summaries, target_fields, targets_for
from apps.admin_center.backend.schemas import ExtractionPreviewSchema, ExtractionRulePatchSchema
from apps.admin_center.backend.services import field_preview, model_dump, safe_rule_domain


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
