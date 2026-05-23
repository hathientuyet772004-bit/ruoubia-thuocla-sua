from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException

from apps.admin_center.backend.dependencies import mongo_store, raw_artifacts, require_admin_session, require_mutation_session
from apps.admin_center.backend.rule_catalog import targets_for
from apps.admin_center.backend.schemas import SourceSchema
from apps.admin_center.backend.services import model_dump, source_group

router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=[Depends(require_admin_session)])


@router.get("")
async def get_all_sources():
    sources = mongo_store.list_sources()
    result = []
    for source in sources:
        domain = source.get("domain") or urlparse(source.get("url") or "").netloc
        result.append({
            "id": source["id"],
            "name": source.get("name"),
            "url": source.get("url"),
            "type": source.get("type"),
            "category": source.get("category"),
            "group": source_group(source.get("category")),
            "note": source.get("note"),
            "saved_locally": bool(mongo_store.raw_pages(domain, 1)),
        })
    return result


@router.post("")
async def create_source(source: SourceSchema, role: str = Depends(require_mutation_session)):
    created = mongo_store.create_source(model_dump(source))
    if not created:
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not create source")
    return created


@router.get("/{source_id}/discovery")
async def get_source_discovery(source_id: str):
    sources = mongo_store.list_sources()
    source = next((row for row in sources if str(row.get("id")) == str(source_id)), None)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    domain = source.get("domain") or urlparse(source.get("url") or "").netloc
    artifacts = raw_artifacts(domain, limit=12)
    rule = mongo_store.rule_structure(domain)
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


@router.put("/{source_id}")
async def update_source(source_id: str, source: SourceSchema, role: str = Depends(require_mutation_session)):
    db_source = mongo_store.update_source(source_id, model_dump(source))
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    return db_source


@router.delete("/{source_id}")
async def delete_source(source_id: str, role: str = Depends(require_mutation_session)):
    if not mongo_store.delete_source(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "deleted"}
