from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.rule_catalog import targets_for
from apps.admin_center.backend.services import source_group


def list_sources() -> list[dict]:
    result = []
    for source in deps.mongo_store.list_sources():
        domain = source.get("domain") or urlparse(source.get("url") or "").netloc
        result.append({
            "id": source["id"],
            "name": source.get("name"),
            "url": source.get("url"),
            "type": source.get("type"),
            "category": source.get("category"),
            "group": source_group(source.get("category")),
            "note": source.get("note"),
            "saved_locally": bool(deps.mongo_store.raw_pages(domain, 1)),
        })
    return result


def source_discovery(source_id: str) -> dict:
    source = next((row for row in deps.mongo_store.list_sources() if str(row.get("id")) == str(source_id)), None)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    domain = source.get("domain") or urlparse(source.get("url") or "").netloc
    artifacts = deps.raw_artifacts(domain, limit=12)
    rule = deps.mongo_store.rule_structure(domain)
    structure = rule.get("structure") if rule else None
    targets = targets_for(structure) if isinstance(structure, dict) else []
    return {
        "source": source,
        "domain": domain,
        "raw_artifacts": artifacts,
        "rule": {
            "configured": bool(rule),
            "version": rule.get("version") if rule else None,
            "targets": targets,
        },
        "summary": {
            "raw_artifact_count": len(artifacts),
            "has_recent_raw": bool(artifacts),
            "has_rule": bool(rule),
        },
    }
