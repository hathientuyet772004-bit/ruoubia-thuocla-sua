from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from apps.admin_center.backend import product_service
from apps.admin_center.backend.dependencies import require_admin_session

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(require_admin_session)])


@router.get("/search")
async def search_products(q: str = None, category: str = "all", source: str = "all", store: str = None, limit: int = 50):
    return product_service.search_products(q, category, source, limit, store)


@router.get("/export")
async def export_products(q: str = None, category: str = "all", source: str = "all", store: str = None, limit: int = 5000):
    products = product_service.search_products(q, category, source, limit, store)
    filename = f"product-price-list-{product_service.local_timestamp()}.csv"
    return Response(
        content=product_service.products_to_csv(products),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
