from __future__ import annotations

import json
import os
from datetime import datetime

from apps.admin_center.backend import dependencies as deps


def search_products(q: str | None = None, category: str = "all", source: str = "all", limit: int = 50) -> list[dict]:
    mongo_products = deps.mongo_store.list_products(query_text=q, category=category, source=source, limit=limit)
    if mongo_products:
        return mongo_products

    results = []
    output_dir = deps.project_root / "store" / "outputs"
    if not output_dir.exists():
        return results

    for path in output_dir.glob("**/*.json"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue

        src = data.get("source_site", path.parent.name)
        for product in data.get("products", []):
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

    results.sort(key=lambda row: row["updated_at"], reverse=True)
    return results[:limit]
