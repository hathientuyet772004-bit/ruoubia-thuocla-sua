from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.admin_center.backend import source_service
from apps.admin_center.backend.dependencies import mongo_store, require_admin_session, require_mutation_session
from apps.admin_center.backend.schemas import SourceSchema
from apps.admin_center.backend.services import model_dump

router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=[Depends(require_admin_session)])


@router.get("")
async def get_all_sources():
    return source_service.list_sources()


@router.post("")
async def create_source(source: SourceSchema, role: str = Depends(require_mutation_session)):
    created = mongo_store.create_source(model_dump(source))
    if not created:
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not create source")
    return created


@router.get("/{source_id}/discovery")
async def get_source_discovery(source_id: str):
    return source_service.source_discovery(source_id)


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
