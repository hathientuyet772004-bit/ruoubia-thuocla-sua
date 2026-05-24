from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.admin_center.backend import product_service
from apps.admin_center.backend.dependencies import require_admin_session

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(require_admin_session)])


@router.get("/search")
async def search_products(q: str = None, category: str = "all", source: str = "all", limit: int = 50):
    return product_service.search_products(q, category, source, limit)
