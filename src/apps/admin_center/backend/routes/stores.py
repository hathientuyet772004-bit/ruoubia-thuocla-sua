from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from apps.admin_center.backend import store_service
from apps.admin_center.backend.dependencies import require_admin_session

router = APIRouter(prefix="/api/stores", tags=["stores"], dependencies=[Depends(require_admin_session)])


@router.get("/search")
async def search_stores(q: str = None, source: str = "all", limit: int = 200):
    return store_service.search_stores(q, source, limit)


@router.get("/export")
async def export_stores(q: str = None, source: str = "all", limit: int = 5000):
    stores = store_service.search_stores(q, source, limit)
    filename = f"store-list-{store_service.local_timestamp()}.csv"
    return Response(
        content=store_service.stores_to_csv(stores),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
