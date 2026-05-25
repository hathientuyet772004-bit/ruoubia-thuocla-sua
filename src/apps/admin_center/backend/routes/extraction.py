from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from apps.admin_center.backend import extraction_service
from apps.admin_center.backend.dependencies import raw_artifacts, require_admin_session, require_mutation_session
from apps.admin_center.backend.schemas import ExtractionPreviewSchema, ExtractionRulePatchSchema, GeminiExtractionAnalyzeSchema

router = APIRouter(prefix="/api/extraction", tags=["extraction"], dependencies=[Depends(require_admin_session)])


@router.get("/rules")
async def list_extraction_rules():
    return extraction_service.list_rules()


@router.get("/raw-artifacts")
async def list_raw_artifacts(domain: str | None = None, limit: int = Query(default=80, ge=1, le=500)):
    return raw_artifacts(domain, limit)


@router.get("/raw-artifacts/{artifact_id}")
async def get_raw_artifact_detail(artifact_id: str, domain: str | None = None):
    return extraction_service.raw_artifact_detail(artifact_id, domain)


@router.get("/rules/{domain}")
async def get_extraction_rule(domain: str, target: str = "product_detail", raw_artifact_id: str | None = None):
    return extraction_service.rule_detail(domain, target, raw_artifact_id)


@router.post("/rules/{domain}/preview")
async def preview_extraction_rule(domain: str, payload: ExtractionPreviewSchema):
    return extraction_service.preview_rule(domain, payload)


@router.patch("/rules/{domain}")
async def save_extraction_rule(
    domain: str,
    payload: ExtractionRulePatchSchema,
    role: str = Depends(require_mutation_session),
):
    return extraction_service.save_rule(domain, payload, role)


@router.post("/ai/analyze")
async def analyze_extraction_with_gemini(payload: GeminiExtractionAnalyzeSchema):
    return extraction_service.analyze_with_gemini(payload)
