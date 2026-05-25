from __future__ import annotations

import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.cache import store_cache

STORE_EXPORT_COLUMNS = ["name", "source", "address", "phone", "url", "latitude", "longitude", "product_count", "updated_at"]
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def search_stores(q: str | None = None, source: str = "all", limit: int = 200) -> list[dict]:
    key = ("stores", q or "", source or "all", int(limit))
    return store_cache.get_or_set(key, lambda: _search_stores_uncached(q, source, limit))


def _search_stores_uncached(q: str | None = None, source: str = "all", limit: int = 200) -> list[dict]:
    mongo_stores = deps.mongo_store.list_stores(query_text=q, source=source, limit=limit)
    rows = deps.load_output_stores(limit=limit * 4 if limit else 600)
    combined: list[dict] = []
    seen: set[str] = set()

    def add_rows(source_rows: list[dict]) -> None:
        for store in source_rows:
            identity = str(store.get("id") or store.get("url") or store.get("name") or "")
            if not identity or identity in seen:
                continue
            seen.add(identity)
            combined.append(store)

    add_rows(mongo_stores)
    add_rows(rows)

    filtered = []
    for store in combined:
        if source and source != "all" and store.get("source") != source:
            continue
        if q:
            haystack = " ".join(str(store.get(field) or "") for field in ["name", "source", "address", "phone", "url"])
            if q.lower() not in haystack.lower():
                continue
        filtered.append(store)
        if len(filtered) >= limit:
            break
    return filtered


def stores_to_csv(stores: list[dict]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=STORE_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for store in stores:
        writer.writerow({
            "name": store.get("name") or "",
            "source": store.get("source") or "",
            "address": store.get("address") or "",
            "phone": store.get("phone") or "",
            "url": store.get("url") or "",
            "latitude": store.get("latitude") or "",
            "longitude": store.get("longitude") or "",
            "product_count": store.get("product_count") or 0,
            "updated_at": store.get("updated_at") or "",
        })
    return output.getvalue()


def local_timestamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")
