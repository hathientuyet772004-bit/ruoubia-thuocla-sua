from __future__ import annotations

import json
import os
from datetime import datetime

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.cache import dashboard_cache


def global_stats() -> dict:
    """Dashboard stats are expensive because they aggregate several Mongo collections."""
    return dashboard_cache.get_or_set(("global_stats",), _global_stats_uncached)


def _global_stats_uncached() -> dict:
    stats = {
        "products": deps.mongo_store.product_stats(),
        "files": deps.mongo_store.job_counts(),
        "system": {"db_status": "MongoDB Atlas", "storage": "MongoDB raw pages / GridFS"},
    }

    if not stats["products"]["total"]:
        output_dir = deps.project_root / "store" / "outputs"
        if output_dir.exists():
            stats["products"]["total"] = len(list(output_dir.glob("*.json")))

    if not sum(stats["files"].values()):
        raw_dir = deps.project_root / "store" / "raw"
        output_dir = deps.project_root / "store" / "outputs"
        all_meta = list(raw_dir.glob("**/*.meta.json")) if raw_dir.exists() else []
        all_outputs = list(output_dir.glob("*.json")) if output_dir.exists() else []
        stats["files"]["completed"] = len(all_outputs)
        stats["files"]["pending"] = max(0, len(all_meta) - len(all_outputs))
        stats["files"]["failed"] = len(list(raw_dir.glob("**/*.error"))) if raw_dir.exists() else 0

    stats["market"] = deps.market_stats()
    return stats


def price_trends() -> list[dict]:
    return dashboard_cache.get_or_set(("price_trends",), deps.price_history_months)


def source_comparison() -> list[dict]:
    return dashboard_cache.get_or_set(("source_comparison",), deps.mongo_store.source_price_comparison)


def recent_products(limit: int = 10, source: str | None = None) -> list[dict]:
    """Cache recent products separately per limit/source filter."""
    return dashboard_cache.get_or_set(("recent_products", int(limit), source or ""), lambda: _recent_products_uncached(limit, source))


def _recent_products_uncached(limit: int = 10, source: str | None = None) -> list[dict]:
    result = deps.mongo_store.recent_products(limit, source)
    if result:
        return result

    products = []
    output_dir = deps.project_root / "store" / "outputs"
    if not output_dir.exists():
        return products

    for path in sorted(output_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue

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
    return products[:limit]


def product_sources() -> list[str]:
    return dashboard_cache.get_or_set(("product_sources",), _product_sources_uncached)


def _product_sources_uncached() -> list[str]:
    result = deps.mongo_store.product_sources()
    if len(result) > 1:
        return result

    raw_dir = deps.project_root / "store" / "raw"
    sources = ["all"]
    if raw_dir.exists():
        for path in raw_dir.iterdir():
            if path.is_dir() and path.name != "misc":
                sources.append(path.name)
    return sources
