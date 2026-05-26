from __future__ import annotations

import logging
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from gridfs import GridFS
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

from apps.admin_center.backend.settings import settings

log = logging.getLogger("admin_center.mongo_store")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AdminMongoStore:
    """Mongo Atlas access layer for Admin Center views and mutations."""

    def __init__(self) -> None:
        self.client: MongoClient | None = None
        self._db: Database | None = None
        self._indexes_ready = False

    def get_db(self) -> Database | None:
        if self._db is not None:
            return self._db
        if not settings.MONGODB_URI:
            log.warning("MONGODB_URI is not configured; Admin Center Mongo data is unavailable.")
            return None
        try:
            self.client = MongoClient(
                settings.MONGODB_URI,
                server_api=ServerApi("1"),
                serverSelectionTimeoutMS=settings.MONGODB_TIMEOUT_MS,
            )
            self._db = self.client[settings.MONGODB_DB]
            self.ensure_indexes()
        except PyMongoError as exc:
            log.error("Admin Center Mongo connection failed: %s", exc)
            self.close()
        return self._db

    def ensure_indexes(self) -> bool:
        db = self._db
        if db is None or self._indexes_ready:
            return db is not None
        try:
            db.sources.create_index("source_id", unique=True)
            db.sources.create_index("domain")
            db.sc_products.create_index([("updated_at", DESCENDING)])
            db.sc_products.create_index("domain")
            db.sc_products.create_index("store_id")
            db.sc_products.create_index("store_name")
            db.sc_products.create_index("store_url")
            db.sc_stores.create_index([("updated_at", DESCENDING)])
            db.sc_stores.create_index("domain")
            db.sc_store_locations.create_index("store_id")
            db.sc_store_locations.create_index("domain")
            db.sc_offers.create_index([("updated_at", DESCENDING)])
            db.sc_raw_pages.create_index("raw_page_id", unique=True)
            db.sc_raw_pages.create_index([("domain", ASCENDING), ("captured_at", DESCENDING)])
            db.sc_crawl_tasks.create_index([("status", ASCENDING), ("updated_at", DESCENDING)])
            db.admin_dedup_candidates.create_index("candidate_id", unique=True)
            db.admin_ai_review_candidates.create_index("review_id", unique=True)
            db.admin_ai_review_candidates.create_index([("domain", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)])
            db.admin_extraction_rules.create_index("domain", unique=True)
            db.admin_rule_events.create_index([("domain", ASCENDING), ("created_at", DESCENDING)])
            db.admin_pipelines.create_index("pipeline_id", unique=True)
            db.admin_pipelines.create_index([("enabled", ASCENDING), ("updated_at", DESCENDING)])
            db.admin_pipeline_runs.create_index("run_id", unique=True)
            db.admin_pipeline_runs.create_index([("pipeline_id", ASCENDING), ("created_at", DESCENDING)])
            db.admin_pipeline_runs.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
            db.admin_pipeline_worker_events.create_index([("pipeline_id", ASCENDING), ("created_at", DESCENDING)])
            self._indexes_ready = True
            return True
        except PyMongoError as exc:
            log.error("Admin Center Mongo index initialization failed: %s", exc)
            return False

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
        self.client = None
        self._db = None
        self._indexes_ready = False

    def ready(self) -> bool:
        db = self.get_db()
        if db is None:
            return False
        try:
            db.command("ping")
            return self.ensure_indexes()
        except PyMongoError as exc:
            log.error("Admin Center Mongo readiness failed: %s", exc)
            self.close()
            return False

    # Source registry

    def seed_sources(self, rows: list[dict[str, Any]]) -> int:
        db = self.get_db()
        if db is None or db.sources.count_documents({}, limit=1):
            return 0
        inserted = 0
        for row in rows:
            if not row.get("name") or not row.get("url"):
                continue
            self.create_source(row)
            inserted += 1
        return inserted

    def list_sources(self, limit: int = 500) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        return [
            self._source_view(doc)
            for doc in db.sources.find({}, {"_id": False}).sort("updated_at", DESCENDING).limit(limit)
        ]

    def create_source(self, source: dict[str, Any]) -> dict[str, Any] | None:
        db = self.get_db()
        payload = self._source_payload(source)
        if db is None:
            return None
        db.sources.insert_one(payload)
        return self._source_view(payload)

    def update_source(self, source_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        current = db.sources.find_one({"source_id": source_id})
        if current is None:
            return None
        payload = self._source_payload({**current, **updates, "source_id": source_id})
        db.sources.update_one({"source_id": source_id}, {"$set": payload})
        return self._source_view(payload)

    def delete_source(self, source_id: str) -> bool:
        db = self.get_db()
        return bool(db is not None and db.sources.delete_one({"source_id": source_id}).deleted_count)

    def _source_payload(self, source: dict[str, Any]) -> dict[str, Any]:
        url = source.get("url") or source.get("base_url") or ""
        domain = source.get("domain") or urlparse(url).netloc
        created_at = source.get("created_at") or now_utc()
        return {
            "source_id": str(source.get("source_id") or source.get("id") or uuid.uuid4()),
            "name": source.get("name"),
            "url": url,
            "base_url": url,
            "domain": domain,
            "type": source.get("type") or source.get("source_type") or "Website",
            "category": source.get("category") or ", ".join(source.get("target_categories", [])),
            "target_categories": source.get("target_categories", []),
            "note": source.get("note") or source.get("notes"),
            "enabled": source.get("enabled", True),
            "created_at": created_at,
            "updated_at": now_utc(),
        }

    def _source_view(self, doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(doc.get("source_id") or doc.get("id")),
            "name": doc.get("name"),
            "url": doc.get("url") or doc.get("base_url"),
            "type": doc.get("type") or doc.get("source_type"),
            "category": doc.get("category") or ", ".join(doc.get("target_categories", [])),
            "note": doc.get("note") or doc.get("notes"),
            "domain": doc.get("domain"),
        }

    # Products and market views

    # Extraction rules

    def seed_rule_structures(self, structures: list[dict[str, Any]]) -> int:
        db = self.get_db()
        if db is None:
            return 0
        inserted = 0
        for structure in structures:
            domain = str(structure.get("domain") or "").strip().lower()
            if not domain:
                continue
            version = self.rule_version(structure)
            result = db.admin_extraction_rules.update_one(
                {"domain": domain},
                {
                    "$setOnInsert": {
                        "domain": domain,
                        "structure": structure,
                        "version": version,
                        "created_at": now_utc(),
                        "updated_at": now_utc(),
                    }
                },
                upsert=True,
            )
            inserted += int(bool(result.upserted_id))
        return inserted

    def list_rule_structures(self) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        return list(db.admin_extraction_rules.find({}, {"_id": False}).sort("updated_at", DESCENDING))

    def rule_structure(self, domain: str) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        return db.admin_extraction_rules.find_one({"domain": domain}, {"_id": False})

    def save_rule_structure(self, domain: str, structure: dict[str, Any], expected_version: str | None) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        current = db.admin_extraction_rules.find_one({"domain": domain}, {"_id": False})
        if current is None and expected_version:
            return None
        if expected_version and current.get("version") != expected_version:
            return {"conflict": True, "version": current.get("version")}
        version = self.rule_version(structure)
        db.admin_extraction_rules.update_one(
            {"domain": domain},
            {
                "$set": {"structure": structure, "version": version, "updated_at": now_utc()},
                "$setOnInsert": {"domain": domain, "created_at": now_utc()},
            },
            upsert=True,
        )
        return {"domain": domain, "structure": structure, "version": version}

    @staticmethod
    def rule_version(structure: dict[str, Any]) -> str:
        raw = json.dumps(structure, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    # Products and market views

    def product_stats(self) -> dict[str, int]:
        db = self.get_db()
        if db is None:
            return {"total": 0, "sources": 0}
        return {
            "total": db.sc_products.count_documents({}),
            "sources": len(db.sc_products.distinct("domain")),
        }

    def list_products(
        self,
        *,
        query_text: str | None = None,
        category: str | None = None,
        source: str | None = None,
        store: str | None = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        query: dict[str, Any] = {}
        if source and source != "all":
            query["domain"] = source
        if category and category != "all":
            query["$or"] = [{"category": category}, {"normalized_category": category}]
        if store:
            store_expr = {"$regex": store, "$options": "i"}
            store_clause = {
                "$or": [
                    {"store_id": store_expr},
                    {"store_name": store_expr},
                    {"store_url": store_expr},
                    {"raw_data.store_id": store_expr},
                    {"raw_data.store_name": store_expr},
                    {"raw_data.store_url": store_expr},
                ]
            }
            query = {"$and": [query, store_clause]} if query else store_clause
        if query_text:
            name_expr = {"$regex": query_text, "$options": "i"}
            text_clause = {"$or": [{"product_name": name_expr}, {"name": name_expr}, {"canonical_name": name_expr}]}
            if "$or" in query:
                query = {"$and": [query, text_clause]}
            else:
                query.update(text_clause)
        docs = db.sc_products.find(query, {"_id": False}).sort("updated_at", DESCENDING).limit(limit)
        return [self._product_view(doc) for doc in docs]

    def recent_products(self, limit: int = 10, source: str | None = None) -> list[dict[str, Any]]:
        return self.list_products(source=source, limit=limit)

    def product_sources(self) -> list[str]:
        db = self.get_db()
        if db is None:
            return ["all"]
        return ["all"] + sorted(source for source in db.sc_products.distinct("domain") if source)

    def market_stats(self) -> dict[str, Any]:
        products = self.list_products(limit=5000)
        prices = []
        for row in products:
            try:
                if row.get("price_numeric"):
                    prices.append(float(row["price_numeric"]))
            except (TypeError, ValueError):
                continue
        history = self.price_history_months()
        trend = "N/A (Can lich su gia)"
        if len(history) >= 2 and history[-2]["avg_price"]:
            previous = history[-2]["avg_price"]
            change = ((history[-1]["avg_price"] - previous) / previous) * 100
            trend = f"{change:+.1f}% ({history[-2]['month']} -> {history[-1]['month']})"
        return {
            "avg_price": round(sum(prices) / len(prices), 0) if prices else 0,
            "currency": "VND",
            "trend": trend,
        }

    def source_price_comparison(self, limit: int = 5000) -> list[dict[str, Any]]:
        products = self.list_products(limit=limit)
        by_source: dict[str, list[float]] = {}
        for row in products:
            source = row.get("source") or row.get("source_site")
            if not source:
                continue
            try:
                price = float(row.get("price_numeric") or row.get("price") or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            by_source.setdefault(source, []).append(price)
        return [
            {"source": source, "avg_price": round(sum(prices) / len(prices), 0), "count": len(prices)}
            for source, prices in sorted(by_source.items())
        ]

    def price_history_months(self, lookback_days: int = 400) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        cutoff = now_utc() - timedelta(days=lookback_days)
        rows = db.sc_offers.find(
            {"price_numeric": {"$gt": 0}, "updated_at": {"$gte": cutoff}},
            {"_id": False, "price_numeric": True, "updated_at": True},
        )
        by_month: dict[str, list[float]] = {}
        for row in rows:
            updated_at = row.get("updated_at")
            if not isinstance(updated_at, datetime):
                continue
            by_month.setdefault(updated_at.strftime("%Y-%m"), []).append(float(row["price_numeric"]))
        return [
            {"month": month, "avg_price": round(sum(prices) / len(prices), 0), "count": len(prices)}
            for month, prices in sorted(by_month.items())
        ]

    def _product_view(self, doc: dict[str, Any]) -> dict[str, Any]:
        price = doc.get("price_numeric", doc.get("price", 0))
        raw_data = doc.get("raw_data") or {}
        return {
            "name": doc.get("product_name") or doc.get("name") or doc.get("canonical_name"),
            "price": price,
            "price_numeric": price,
            "original_price": doc.get("old_price") or doc.get("original_price"),
            "currency": doc.get("currency", "VND"),
            "url": doc.get("product_url") or doc.get("url"),
            "source": doc.get("domain") or doc.get("source_site"),
            "source_site": doc.get("domain") or doc.get("source_site"),
            "category": doc.get("category") or doc.get("normalized_category") or "Khac",
            "image": doc.get("image_url"),
            "image_url": doc.get("image_url"),
            "brand": doc.get("brand"),
            "store_id": doc.get("store_id") or raw_data.get("store_id") or "",
            "store_name": doc.get("store_name") or raw_data.get("store_name") or "",
            "store_url": doc.get("store_url") or raw_data.get("store_url") or "",
            "store_address": doc.get("store_address") or raw_data.get("store_address") or "",
            "store_phone": doc.get("store_phone") or raw_data.get("store_phone") or "",
            "updated_at": doc.get("updated_at") or doc.get("created_at"),
        }

    # Stores and locations

    def list_stores(
        self,
        *,
        query_text: str | None = None,
        source: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        query: dict[str, Any] = {}
        if source and source != "all":
            query["domain"] = source
        if query_text:
            text_expr = {"$regex": query_text, "$options": "i"}
            query["$or"] = [{"store_name": text_expr}, {"name": text_expr}, {"address": text_expr}, {"store_address": text_expr}]
        docs = db.sc_stores.find(query, {"_id": False}).sort("updated_at", DESCENDING).limit(limit)
        stores = [self._store_view(doc) for doc in docs]
        if stores:
            return self._attach_store_product_counts(stores)

        docs = db.sc_store_locations.find(query, {"_id": False}).sort("updated_at", DESCENDING).limit(limit)
        return self._attach_store_product_counts([self._store_view(doc) for doc in docs])

    def _attach_store_product_counts(self, stores: list[dict[str, Any]]) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None or not stores:
            return stores
        for store in stores:
            store["product_count"] = 0

        by_id = {store["id"]: store for store in stores if store.get("id")}
        by_name = {store["name"]: store for store in stores if store.get("name")}
        by_url = {store["url"]: store for store in stores if store.get("url")}
        clauses = []
        if by_id:
            ids = list(by_id)
            clauses.extend([{"store_id": {"$in": ids}}, {"raw_data.store_id": {"$in": ids}}])
        if by_name:
            names = list(by_name)
            clauses.extend([{"store_name": {"$in": names}}, {"raw_data.store_name": {"$in": names}}])
        if by_url:
            urls = list(by_url)
            clauses.extend([{"store_url": {"$in": urls}}, {"raw_data.store_url": {"$in": urls}}])
        if not clauses:
            return stores

        stores_by_identity = {id(store): store for store in stores}
        projection = {
            "_id": False,
            "store_id": True,
            "store_name": True,
            "store_url": True,
            "raw_data.store_id": True,
            "raw_data.store_name": True,
            "raw_data.store_url": True,
        }
        for product in db.sc_products.find({"$or": clauses}, projection):
            raw_data = product.get("raw_data") or {}
            matched = set()
            if product.get("store_id") in by_id:
                matched.add(id(by_id[product["store_id"]]))
            if raw_data.get("store_id") in by_id:
                matched.add(id(by_id[raw_data["store_id"]]))
            if product.get("store_name") in by_name:
                matched.add(id(by_name[product["store_name"]]))
            if raw_data.get("store_name") in by_name:
                matched.add(id(by_name[raw_data["store_name"]]))
            if product.get("store_url") in by_url:
                matched.add(id(by_url[product["store_url"]]))
            if raw_data.get("store_url") in by_url:
                matched.add(id(by_url[raw_data["store_url"]]))
            for store_identity in matched:
                stores_by_identity[store_identity]["product_count"] += 1
        return stores

    def _store_view(self, doc: dict[str, Any]) -> dict[str, Any]:
        metadata = doc.get("metadata") or {}
        return {
            "id": str(doc.get("store_id") or doc.get("location_id") or doc.get("id") or ""),
            "name": doc.get("store_name") or doc.get("name") or metadata.get("store_name"),
            "source": doc.get("domain") or doc.get("source_site") or metadata.get("domain"),
            "address": doc.get("store_address") or doc.get("address") or metadata.get("address"),
            "phone": doc.get("store_phone") or doc.get("phone") or metadata.get("phone"),
            "url": doc.get("store_url") or doc.get("url") or metadata.get("url"),
            "latitude": doc.get("latitude") or doc.get("lat"),
            "longitude": doc.get("longitude") or doc.get("lng") or doc.get("lon"),
            "product_count": doc.get("product_count", 0),
            "updated_at": doc.get("updated_at") or doc.get("created_at") or doc.get("captured_at"),
        }

    # Raw pages and jobs

    def raw_pages(self, domain: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        query = {"domain": domain} if domain else {}
        docs = db.sc_raw_pages.find(query, {"_id": False, "content": False}).sort("captured_at", DESCENDING).limit(limit)
        return [self._raw_page_view(doc) for doc in docs]

    def raw_page_domains(self, domains: list[str]) -> set[str]:
        """Return domains that already have raw pages using one MongoDB query."""
        db = self.get_db()
        if db is None or not domains:
            return set()
        aliases = set(domains)
        for domain in domains:
            aliases.add(domain.removeprefix("www."))
            if not domain.startswith("www."):
                aliases.add(f"www.{domain}")
        return set(db.sc_raw_pages.distinct("domain", {"domain": {"$in": list(aliases)}}))

    def raw_page(self, raw_page_id: str | None, domain: str | None = None) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        query: dict[str, Any] = {"raw_page_id": raw_page_id} if raw_page_id else {}
        if domain:
            query["domain"] = domain
        return db.sc_raw_pages.find_one(query, {"_id": False}, sort=[("captured_at", DESCENDING)])

    def raw_page_html(self, doc: dict[str, Any] | None) -> str | None:
        if not doc:
            return None
        content = doc.get("content") or doc.get("html") or doc.get("mhtml")
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        if isinstance(content, str):
            return content
        file_id = doc.get("gridfs_file_id")
        db = self.get_db()
        if db is None or file_id is None:
            return None
        try:
            return GridFS(db).get(file_id).read().decode("utf-8", errors="replace")
        except Exception as exc:
            log.warning("Could not read GridFS raw page %s: %s", doc.get("raw_page_id"), exc)
            return None

    def save_raw_page_content(self, raw_page: dict[str, Any], content: bytes) -> dict[str, Any]:
        db = self.get_db()
        payload = {
            **raw_page,
            "raw_page_id": raw_page.get("raw_page_id") or str(uuid.uuid4()),
            "domain": raw_page.get("domain") or "unknown",
            "content_type": raw_page.get("content_type", "mhtml"),
            "content_length": len(content),
            "captured_at": raw_page.get("captured_at") or now_utc(),
        }
        if db is None:
            return payload
        file_id = GridFS(db).put(
            content,
            filename=payload.get("metadata", {}).get("filename") or f"{payload['raw_page_id']}.mhtml",
            content_type=payload["content_type"],
        )
        payload["gridfs_file_id"] = file_id
        db.sc_raw_pages.update_one(
            {"raw_page_id": payload["raw_page_id"]},
            {"$set": payload, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True,
        )
        return payload

    def job_counts(self) -> dict[str, int]:
        db = self.get_db()
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        if db is None:
            return counts
        for row in db.sc_crawl_tasks.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]):
            normalized = {"running": "processing", "done": "completed"}.get(row.get("_id"), row.get("_id"))
            if normalized in counts:
                counts[normalized] = row.get("count", 0)
        return counts

    def jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        pages = self.raw_pages(limit=limit)
        return [
            {
                "id": page["task_id"] or page["id"],
                "filename": page["filename"],
                "source": page["domain"],
                "status": page.get("status", "Pending"),
                "timestamp": page["updated_at"],
            }
            for page in pages
        ]

    def job_log(self, job_id: str) -> dict[str, Any] | None:
        db = self.get_db()
        local_raw_dir = Path(__file__).resolve().parents[4] / "store" / "raw"
        local_meta_files = list(local_raw_dir.glob(f"**/{job_id}.meta.json")) if local_raw_dir.exists() else []
        local_meta: dict[str, Any] = {}
        local_error: str | None = None
        if local_meta_files:
            meta_file = local_meta_files[0]
            try:
                with open(meta_file, "r", encoding="utf-8") as handle:
                    local_meta = json.load(handle)
            except Exception:
                local_meta = {}
            error_file = meta_file.parent / f"{job_id}.error"
            if error_file.exists():
                with open(error_file, "r", encoding="utf-8") as handle:
                    local_error = handle.read()
        if db is None:
            if local_meta_files:
                return {
                    "job_id": job_id,
                    "events": [f"[{local_meta.get('captured_at') or datetime.fromtimestamp(local_meta_files[0].stat().st_mtime).isoformat()}] Raw file discovered."],
                    "metadata": local_meta,
                    "error": local_error,
                    "output_summary": None,
                }
            return None
        page = db.sc_raw_pages.find_one({"$or": [{"task_id": job_id}, {"raw_page_id": job_id}]}, {"_id": False})
        task = db.sc_crawl_tasks.find_one({"task_id": job_id}, {"_id": False})
        if page is None and task is None and not local_meta_files:
            return None
        events = []
        if page:
            events.append(f"[{page.get('captured_at')}] Raw page captured.")
        elif local_meta_files:
            events.append(f"[{local_meta.get('captured_at') or datetime.fromtimestamp(local_meta_files[0].stat().st_mtime).isoformat()}] Raw file discovered.")
        if task:
            events.append(f"[{task.get('updated_at') or task.get('created_at')}] Task status: {task.get('status')}.")
        elif local_error:
            events.append(f"[{datetime.fromtimestamp(local_meta_files[0].stat().st_mtime).isoformat()}] Processing failed.")
        return {
            "job_id": job_id,
            "events": events,
            "metadata": page.get("metadata", {}) if page else local_meta,
            "error": task.get("last_error") if task else local_error,
            "output_summary": task.get("output_summary") if task else None,
        }

    # Admin workflow state

    def sync_dedup_candidates(self, candidates: list[dict[str, Any]]) -> None:
        db = self.get_db()
        if db is None:
            return
        for candidate in candidates:
            db.admin_dedup_candidates.update_one(
                {"candidate_id": candidate["id"]},
                {
                    "$set": {**candidate, "candidate_id": candidate["id"], "updated_at": now_utc()},
                    "$setOnInsert": {"status": "pending", "created_at": now_utc()},
                },
                upsert=True,
            )

    def list_dedup_candidates(self, status: str | None, limit: int) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        query = {} if not status or status == "all" else {"status": status}
        rows = db.admin_dedup_candidates.find(query, {"_id": False, "candidate_id": False})
        return list(rows.sort([("status", ASCENDING), ("confidence", DESCENDING)]).limit(limit))

    def update_dedup_candidate(self, candidate_id: str, status: str, note: str | None, role: str) -> bool:
        db = self.get_db()
        if db is None:
            return False
        result = db.admin_dedup_candidates.update_one(
            {"candidate_id": candidate_id},
            {"$set": {"status": status, "note": note, "updated_by_role": role, "updated_at": now_utc()}},
        )
        return bool(result.matched_count)

    def sync_ai_review_candidates(self, candidates: list[dict[str, Any]]) -> None:
        db = self.get_db()
        if db is None:
            return
        for candidate in candidates:
            review_id = candidate.get("review_id") or candidate.get("id")
            if not review_id:
                continue
            db.admin_ai_review_candidates.update_one(
                {"review_id": review_id},
                {
                    "$set": {**candidate, "review_id": review_id, "updated_at": now_utc()},
                    "$setOnInsert": {"status": candidate.get("review_status") or "needs_review", "created_at": now_utc()},
                },
                upsert=True,
            )

    def list_ai_review_candidates(self, status: str | None, domain: str | None, limit: int) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        query: dict[str, Any] = {}
        if status and status != "all":
            query["status"] = status
        if domain and domain != "all":
            query["domain"] = domain
        rows = db.admin_ai_review_candidates.find(query, {"_id": False, "review_id": False})
        return list(rows.sort([("status", ASCENDING), ("confidence", DESCENDING), ("updated_at", DESCENDING)]).limit(limit))

    def update_ai_review_candidate(self, review_id: str, status: str, note: str | None, role: str) -> bool:
        db = self.get_db()
        if db is None:
            return False
        result = db.admin_ai_review_candidates.update_one(
            {"review_id": review_id},
            {"$set": {"status": status, "note": note, "updated_by_role": role, "updated_at": now_utc()}},
        )
        return bool(result.matched_count)

    def ai_review_candidate(self, review_id: str) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        return db.admin_ai_review_candidates.find_one({"review_id": review_id}, {"_id": False})

    def record_rule_event(self, event: dict[str, Any]) -> None:
        db = self.get_db()
        if db is not None:
            db.admin_rule_events.insert_one(dict(event))

    def _raw_page_view(self, doc: dict[str, Any]) -> dict[str, Any]:
        metadata = doc.get("metadata", {})
        content_type = doc.get("content_type", "mhtml")
        captured_at = doc.get("captured_at") or doc.get("created_at") or now_utc()
        status = doc.get("status") or metadata.get("status") or "pending"
        return {
            "id": doc.get("raw_page_id"),
            "filename": metadata.get("filename") or f"{doc.get('raw_page_id')}.{content_type}",
            "path": f"mongodb://sc_raw_pages/{doc.get('raw_page_id')}",
            "domain": doc.get("domain") or metadata.get("domain") or doc.get("source_id") or "unknown",
            "task_id": doc.get("task_id") or doc.get("raw_page_id"),
            "url": doc.get("url"),
            "page_type": metadata.get("page_type", doc.get("page_type", "unknown")),
            "size": doc.get("content_length") or metadata.get("size"),
            "updated_at": captured_at,
            "status": {
                "pending": "Pending",
                "running": "Processing",
                "processing": "Processing",
                "done": "Completed",
                "completed": "Completed",
                "failed": "Failed",
            }.get(str(status).lower(), str(status).title()),
        }
