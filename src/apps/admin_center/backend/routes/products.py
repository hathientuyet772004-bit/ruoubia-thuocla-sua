from __future__ import annotations

import json
import os
from datetime import datetime

from fastapi import APIRouter

from apps.admin_center.backend.dependencies import mongo_store, project_root

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/search")
async def search_products(q: str = None, category: str = "all", source: str = "all", limit: int = 50):
    mongo_products = mongo_store.list_products(query_text=q, category=category, source=source, limit=limit)
    if mongo_products:
        return mongo_products

    results = []
    output_dir = project_root / "store" / "outputs"

    if output_dir.exists():
        for path in output_dir.glob("**/*.json"):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    raw_products = data.get("products", [])
                    src = data.get("source_site", path.parent.name)

                    for product in raw_products:
                        if source != "all" and src != source:
                            continue
                        name = product.get("name", "")
                        if q and q.lower() not in name.lower():
                            continue
                        product_category = product.get("category", "Khác")
                        if category != "all" and product_category != category:
                            continue

                        results.append({
                            "name": name,
                            "price": product.get("price", 0),
                            "original_price": product.get("original_price"),
                            "url": product.get("url"),
                            "source": src,
                            "category": product_category,
                            "image": product.get("image_url"),
                            "brand": product.get("brand"),
                            "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                        })
            except Exception:
                continue

    results.sort(key=lambda row: row["updated_at"], reverse=True)
    return results[:limit]
