from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.admin_center.backend import dashboard_service
from apps.admin_center.backend.dependencies import require_admin_session

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin_session)])


@router.get("/stats")
async def get_global_stats():
    return dashboard_service.global_stats()


@router.get("/trends")
async def get_price_trends():
    return dashboard_service.price_trends()


@router.get("/comparison")
async def get_source_comparison():
    return dashboard_service.source_comparison()


@router.get("/recent-products")
async def get_recent_products(limit: int = 10, source: str = None):
    return dashboard_service.recent_products(limit, source)


@router.get("/sources")
async def get_sources():
    return dashboard_service.product_sources()
