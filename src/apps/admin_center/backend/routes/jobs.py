from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.admin_center.backend import job_service
from apps.admin_center.backend.dependencies import require_admin_session

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(require_admin_session)])


@router.get("")
async def get_jobs(limit: int = 50):
    return job_service.list_jobs(limit)


@router.get("/logs/{job_id}")
async def get_job_logs(job_id: str):
    return job_service.job_logs(job_id)
