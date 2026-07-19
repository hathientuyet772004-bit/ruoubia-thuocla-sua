from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from apps.admin_center.backend import canonical_service, product_service
from apps.admin_center.backend.dependencies import require_admin_session, require_mutation_session

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(require_admin_session)])


@router.get("/search")
async def search_products(q: str = None, category: str = "all", source: str = "all", store: str = None, limit: int = 50):
    return product_service.search_products(q, category, source, limit, store)


@router.post("/canonicalize")
async def canonicalize_products(limit: int = 5000, min_score: float = 0.88, role: str = Depends(require_mutation_session)):
    return canonical_service.canonicalize_products(limit=limit, min_score=min_score)


@router.get("/export")
async def export_products(q: str = None, category: str = "all", source: str = "all", store: str = None, limit: int = 5000):
    products = product_service.search_products(q, category, source, limit, store)
    filename = f"product-price-list-{product_service.local_timestamp()}.csv"
    content = "\ufeff" + product_service.products_to_csv(products)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
