from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.cache import product_cache
from apps.admin_center.backend.settings import settings

PRODUCT_EXPORT_COLUMNS = [
    "name",
    "price",
    "original_price",
    "currency",
    "price_status",
    "source",
    "category",
    "brand",
    "store_name",
    "store_url",
    "store_address",
    "store_channel",
    "address_status",
    "store_phone",
    "data_origin",
    "rule_version",
    "extraction_method",
    "validation_score",
    "url",
    "updated_at",
]
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def search_products(q: str | None = None, category: str = "all", source: str = "all", limit: int = 50, store: str | None = None) -> list[dict]:
    """Search products with a short cache for repeated UI filter loads."""
    key = ("products", q or "", category or "all", source or "all", store or "", int(limit))
    return product_cache.get_or_set(key, lambda: _search_products_uncached(q, category, source, limit, store))


def _search_products_uncached(q: str | None = None, category: str = "all", source: str = "all", limit: int = 50, store: str | None = None) -> list[dict]:
    mongo_products = deps.mongo_store.list_products(query_text=q, category=category, source=source, store=store, limit=limit)
    if mongo_products:
        return mongo_products
    if not settings.ADMIN_PRODUCT_LOCAL_FALLBACK_ENABLED:
        return []

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
            store_fields = " ".join(
                str(product.get(field) or "")
                for field in ["store_name", "store_url", "store_address", "store_phone"]
            )
            if store and store.lower() not in store_fields.lower():
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
                "store_name": product.get("store_name") or "",
                "store_url": product.get("store_url") or "",
                "store_address": product.get("store_address") or "",
                "store_phone": product.get("store_phone") or "",
                "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
            })

    results.sort(key=lambda row: row["updated_at"], reverse=True)
    return results[:limit]


def products_to_csv(products: list[dict]) -> str:
    """Serialize product and price rows in the same format downloaded by the UI."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PRODUCT_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for product in products:
        writer.writerow({
            "name": product.get("name") or "",
            "price": product.get("price") or product.get("price_numeric") or "",
            "original_price": product.get("original_price") or "",
            "currency": product.get("currency") or "VND",
            "price_status": product.get("price_status") or "",
            "source": product.get("source") or product.get("source_site") or "",
            "category": product.get("category") or "",
            "brand": product.get("brand") or "",
            "store_name": product.get("store_name") or "",
            "store_url": product.get("store_url") or "",
            "store_address": product.get("store_address") or "",
            "store_channel": product.get("store_channel") or "",
            "address_status": product.get("address_status") or "",
            "store_phone": product.get("store_phone") or "",
            "data_origin": product.get("data_origin") or "",
            "rule_version": product.get("rule_version") or "",
            "extraction_method": product.get("extraction_method") or "",
            "validation_score": product.get("validation_score") or "",
            "url": product.get("url") or "",
            "updated_at": product.get("updated_at") or "",
        })
    return output.getvalue()


def local_timestamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")
