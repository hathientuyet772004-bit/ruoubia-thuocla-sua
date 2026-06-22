from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from apps.admin_center.backend import extraction_service, pipeline_service, source_service, worker
from apps.admin_center.backend.dependencies import mongo_store, require_admin_session, require_mutation_session
from apps.admin_center.backend.schemas import SourceSchema, SyntheticBatchDecisionSchema, SyntheticDataGenerateSchema, GenerationPromptSchema
from apps.admin_center.backend.services import model_dump

router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=[Depends(require_admin_session)])
log = logging.getLogger("admin_center.sources")


@router.get("/generation-prompt/latest")
async def get_latest_generation_prompt():
    latest = mongo_store.get_latest_prompt("synthetic_data")
    if not latest:
        from apps.admin_center.backend.gemini_service import get_synthetic_data_prompt_template
        content = get_synthetic_data_prompt_template()
        return {"key": "synthetic_data", "version": 0, "content": content}
    return latest


@router.get("/generation-prompt/versions")
async def get_generation_prompt_versions():
    return mongo_store.list_prompt_versions("synthetic_data")


@router.post("/generation-prompt")
async def save_generation_prompt(payload: GenerationPromptSchema, role: str = Depends(require_mutation_session)):
    doc = mongo_store.save_new_prompt_version("synthetic_data", payload.content)
    if not doc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable")
    return doc


@router.get("")
async def get_all_sources():
    return source_service.list_sources()


@router.post("")
async def create_source(source: SourceSchema, role: str = Depends(require_mutation_session)):
    created = mongo_store.create_source(model_dump(source))
    if not created:
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not create source")
    source_service.clear_source_cache()
    return created


@router.get("/template")
async def download_source_template():
    return _csv_response(source_service.source_template_csv(), "source-import-template.csv")


@router.get("/export")
async def export_sources():
    return _csv_response(source_service.sources_to_csv(source_service.list_sources()), f"source-list-{source_service.local_timestamp()}.csv")


@router.post("/import")
async def import_sources(request: Request, role: str = Depends(require_mutation_session)):
    raw_csv = (await request.body()).decode("utf-8-sig")
    result = source_service.import_sources_csv(raw_csv)
    if result["failed"] and not result["imported"]:
        raise HTTPException(status_code=503, detail="MongoDB Atlas could not import sources")
    source_service.clear_source_cache()
    return result


@router.get("/{source_id}/discovery")
async def get_source_discovery(source_id: str):
    return source_service.source_discovery(source_id)


@router.get("/{source_id}/runs")
async def get_source_runs(source_id: str, limit: int = 20):
    return pipeline_service.list_source_runs(source_id, limit)


def _collect_source_job(pipeline: dict) -> None:
    try:
        pipeline_service.run_collection_pipeline(pipeline["id"], worker.capture_entry_urls)
    except Exception as exc:  # pragma: no cover - background job must not crash the API worker
        log.exception("Source collection failed for %s: %s", pipeline.get("id"), exc)


@router.post("/{source_id}/collect")
async def collect_source(source_id: str, background_tasks: BackgroundTasks, role: str = Depends(require_mutation_session)):
    pipeline = pipeline_service.ensure_source_pipeline(source_id)
    background_tasks.add_task(_collect_source_job, pipeline)
    return {"status": "queued", "pipeline_id": pipeline["id"], "source_id": source_id}


@router.post("/{source_id}/generate-data")
async def generate_source_data(source_id: str, payload: SyntheticDataGenerateSchema, role: str = Depends(require_mutation_session)):
    return extraction_service.generate_source_synthetic_data(source_id, payload)


@router.get("/synthetic-batches")
async def get_synthetic_batches(source_id: str | None = None, status: str | None = None, limit: int = 100):
    return extraction_service.list_synthetic_batches(source_id, status, limit)


@router.put("/{source_id}/synthetic-batches/{batch_id}/decision")
async def decide_synthetic_batch(
    source_id: str,
    batch_id: str,
    payload: SyntheticBatchDecisionSchema,
    role: str = Depends(require_mutation_session),
):
    return extraction_service.update_synthetic_batch_decision(source_id, batch_id, payload, role)


@router.put("/{source_id}")
async def update_source(source_id: str, source: SourceSchema, role: str = Depends(require_mutation_session)):
    db_source = mongo_store.update_source(source_id, model_dump(source))
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")
    source_service.clear_source_cache()
    return db_source


@router.delete("/{source_id}")
async def delete_source(source_id: str, role: str = Depends(require_mutation_session)):
    if not mongo_store.delete_source(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    source_service.clear_source_cache()
    return {"status": "deleted"}


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
