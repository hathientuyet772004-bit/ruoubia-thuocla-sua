from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.admin_center.backend import pipeline_service
from apps.admin_center.backend.dependencies import require_admin_session, require_mutation_session
from apps.admin_center.backend.schemas import PipelineSchema

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"], dependencies=[Depends(require_admin_session)])


@router.get("")
async def get_pipelines():
    return pipeline_service.list_pipelines()


@router.get("/templates")
async def get_pipeline_templates():
    return pipeline_service.list_pipeline_templates()


@router.get("/overview")
async def get_pipeline_overview():
    return pipeline_service.pipeline_overview()


@router.get("/runs")
async def get_pipeline_runs(limit: int = 50, pipeline_id: str | None = None):
    return pipeline_service.list_pipeline_runs(limit, pipeline_id)


@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    pipeline = pipeline_service.get_pipeline(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.post("")
async def create_pipeline(payload: PipelineSchema, role: str = Depends(require_mutation_session)):
    pipeline = pipeline_service.create_pipeline(payload)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="PostgreSQL could not create pipeline")
    return pipeline


@router.put("/{pipeline_id}")
async def update_pipeline(pipeline_id: str, payload: PipelineSchema, role: str = Depends(require_mutation_session)):
    pipeline = pipeline_service.update_pipeline(pipeline_id, payload)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, role: str = Depends(require_mutation_session)):
    if not pipeline_service.delete_pipeline(pipeline_id):
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"status": "deleted"}


@router.post("/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str, role: str = Depends(require_mutation_session)):
    return pipeline_service.run_pipeline(pipeline_id)

