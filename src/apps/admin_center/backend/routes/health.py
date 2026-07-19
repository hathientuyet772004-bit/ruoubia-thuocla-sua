from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.admin_center.backend.dependencies import data_store

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": "Admin Center"}


@router.get("/ready")
async def ready():
    if not data_store.ready():
        raise HTTPException(status_code=503, detail="PostgreSQL database is unavailable")
    return {"status": "ready", "database": "PostgreSQL"}
