from __future__ import annotations

import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend.cache import store_cache

STORE_EXPORT_COLUMNS = ["name", "source", "address", "phone", "url", "latitude", "longitude", "updated_at"]
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def search_stores(q: str | None = None, source: str = "all", limit: int = 200) -> list[dict]:
    key = ("stores", q or "", source or "all", int(limit))
    return store_cache.get_or_set(key, lambda: deps.mongo_store.list_stores(query_text=q, source=source, limit=limit))


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
            "updated_at": store.get("updated_at") or "",
        })
    return output.getvalue()


def local_timestamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")
