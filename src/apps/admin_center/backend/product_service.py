from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.admin_center.backend import dependencies as deps

PRODUCT_EXPORT_COLUMNS = [
    "name",
    "price",
    "original_price",
    "currency",
    "source",
    "category",
    "brand",
    "url",
    "updated_at",
]
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


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


def products_to_csv(products: list[dict]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PRODUCT_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for product in products:
        writer.writerow({
            "name": product.get("name") or "",
            "price": product.get("price") or product.get("price_numeric") or "",
            "original_price": product.get("original_price") or "",
            "currency": product.get("currency") or "VND",
            "source": product.get("source") or product.get("source_site") or "",
            "category": product.get("category") or "",
            "brand": product.get("brand") or "",
            "url": product.get("url") or "",
            "updated_at": product.get("updated_at") or "",
        })
    return output.getvalue()


def local_timestamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")
