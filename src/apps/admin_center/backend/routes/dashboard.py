from __future__ import annotations

import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends

from apps.admin_center.backend.dependencies import market_stats, mongo_store, price_history_months, project_root, require_admin_session

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin_session)])


@router.get("/stats")
async def get_global_stats():
    stats = {
        "products": mongo_store.product_stats(),
        "files": mongo_store.job_counts(),
        "system": {"db_status": "MongoDB Atlas", "storage": "MongoDB raw pages / GridFS"},
    }

    if not stats["products"]["total"]:
        output_dir = project_root / "store" / "outputs"
        if output_dir.exists():
            stats["products"]["total"] = len(list(output_dir.glob("*.json")))

    if not sum(stats["files"].values()):
        raw_dir = project_root / "store" / "raw"
        output_dir = project_root / "store" / "outputs"
        all_meta = list(raw_dir.glob("**/*.meta.json")) if raw_dir.exists() else []
        all_outputs = list(output_dir.glob("*.json")) if output_dir.exists() else []
        stats["files"]["completed"] = len(all_outputs)
        stats["files"]["pending"] = max(0, len(all_meta) - len(all_outputs))
        stats["files"]["failed"] = len(list(raw_dir.glob("**/*.error"))) if raw_dir.exists() else 0

    stats["market"] = market_stats()
    return stats


@router.get("/trends")
async def get_price_trends():
    return price_history_months()


@router.get("/comparison")
async def get_source_comparison():
    return mongo_store.source_price_comparison()


@router.get("/recent-products")
async def get_recent_products(limit: int = 10, source: str = None):
    result = mongo_store.recent_products(limit, source)
    if result:
        return result

    products = []
    output_dir = project_root / "store" / "outputs"
    if output_dir.exists():
        for path in sorted(output_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    source_site = data.get("source_site", path.stem.split("_")[0])
                    if source and source != "all" and source_site != source:
                        continue
                    for product in data.get("products", [])[:2]:
                        products.append({
                            "name": product.get("name"),
                            "price_numeric": product.get("price"),
                            "currency": "VND",
                            "source_site": source_site,
                            "url": product.get("url"),
                            "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                        })
            except Exception:
                continue
    return products[:limit]


@router.get("/sources")
async def get_sources():
    result = mongo_store.product_sources()
    if len(result) > 1:
        return result

    raw_dir = project_root / "store" / "raw"
    sources = ["all"]
    if raw_dir.exists():
        for path in raw_dir.iterdir():
            if path.is_dir() and path.name != "misc":
                sources.append(path.name)
    return sources
