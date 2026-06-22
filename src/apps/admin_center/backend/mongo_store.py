from __future__ import annotations

import logging
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

from gridfs import GridFS
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

from apps.admin_center.backend.settings import settings

log = logging.getLogger("admin_center.mongo_store")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
T = TypeVar("T")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AdminMongoStore:
    """Mongo Atlas access layer for Admin Center views and mutations."""

    def __init__(self) -> None:
        self.client: MongoClient | None = None
        self._db: Database | None = None
        self._indexes_ready = False
        self._index_error: str | None = None
        self._unavailable_until = 0.0
        self._connecting = False
        self._state_lock = RLock()

    def get_db(self) -> Database | None:
        with self._state_lock:
            if self._db is not None:
                return self._db
            if self._connecting or time.monotonic() < self._unavailable_until:
                return None
            self._connecting = True
        if not settings.MONGODB_URI:
            log.warning("MONGODB_URI is not configured; Admin Center Mongo data is unavailable.")
            with self._state_lock:
                self._connecting = False
            return None
        client: MongoClient | None = None
        try:
            client = MongoClient(
                settings.MONGODB_URI,
                server_api=ServerApi("1"),
                serverSelectionTimeoutMS=settings.MONGODB_TIMEOUT_MS,
            )
            db = client[settings.MONGODB_DB]
            db.command("ping")
            with self._state_lock:
                self.client = client
                self._db = db
            self.ensure_indexes()
            return db
        except PyMongoError as exc:
            log.error("Admin Center Mongo connection failed: %s", exc)
            if client is not None:
                client.close()
            self.mark_read_unavailable(exc)
            return None
        finally:
            with self._state_lock:
                self._connecting = False

    def read_or_default(self, operation: str, loader: Callable[[], T], default: T) -> T:
        """Keep read-only Admin Center views available during transient Atlas failures."""
        try:
            return loader()
        except PyMongoError as exc:
            log.warning("Mongo read failed for %s; using fallback: %s", operation, exc)
            self.mark_read_unavailable(exc)
            return default

    def mark_read_unavailable(self, error: object, cooldown_seconds: int = 30) -> None:
        self.close()
        with self._state_lock:
            self._unavailable_until = time.monotonic() + max(1, cooldown_seconds)
        log.warning("Mongo reads paused for %ss: %s", cooldown_seconds, error)

    def connection_status(self) -> dict[str, Any]:
        with self._state_lock:
            db_available = self._db is not None
            connecting = self._connecting
            cooldown_active = time.monotonic() < self._unavailable_until
            index_error = self._index_error
            indexes_ready = self._indexes_ready
        return {
            "db_available": db_available,
            "data_status": "ok" if db_available else "degraded",
            "connecting": connecting,
            "cooldown_active": cooldown_active,
            "indexes_ready": indexes_ready,
            "index_status": "ready" if indexes_ready else "degraded" if index_error else "pending",
            "detail": index_error if db_available and index_error else None,
        }

    def ensure_indexes(self) -> bool:
        db = self._db
        if db is None or self._indexes_ready:
            return db is not None
        try:
            db.sources.create_index("source_id", unique=True)
            db.sources.create_index("domain")
            db.sc_products.create_index([("updated_at", DESCENDING)])
            db.sc_products.create_index("domain")
            db.sc_products.create_index("store_name")
            db.sc_products.create_index("store_url")
            db.sc_offers.create_index([("updated_at", DESCENDING)])
            db.sc_raw_pages.create_index("raw_page_id", unique=True)
            db.sc_raw_pages.create_index([("domain", ASCENDING), ("captured_at", DESCENDING)])
            db.sc_raw_pages.create_index([("url", ASCENDING), ("captured_at", DESCENDING)])
            db.sc_crawl_tasks.create_index([("status", ASCENDING), ("updated_at", DESCENDING)])
            db.admin_dedup_candidates.create_index("candidate_id", unique=True)
            db.admin_ai_review_candidates.create_index("review_id", unique=True)
            db.admin_ai_review_candidates.create_index([("domain", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)])
            db.admin_extraction_rules.create_index("domain", unique=True)
            db.admin_extraction_rule_candidates.create_index("candidate_id", unique=True)
            db.admin_extraction_rule_candidates.create_index([("domain", ASCENDING), ("created_at", DESCENDING)])
            db.admin_extraction_rule_candidates.create_index([("domain", ASCENDING), ("content_hash", ASCENDING)])
            db.admin_rule_generation_attempts.create_index([("domain", ASCENDING), ("content_hash", ASCENDING)], unique=True)
            db.admin_rule_generation_attempts.create_index([("retry_after", ASCENDING)])
            db.admin_extraction_rule_versions.create_index([("domain", ASCENDING), ("created_at", DESCENDING)])
            db.admin_rule_events.create_index([("domain", ASCENDING), ("created_at", DESCENDING)])
            db.admin_pipelines.create_index("pipeline_id", unique=True)
            db.admin_pipelines.create_index([("enabled", ASCENDING), ("updated_at", DESCENDING)])
            db.admin_pipeline_runs.create_index("run_id", unique=True)
            db.admin_pipeline_runs.create_index([("pipeline_id", ASCENDING), ("created_at", DESCENDING)])
            db.admin_pipeline_runs.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
            db.admin_pipeline_worker_events.create_index([("pipeline_id", ASCENDING), ("created_at", DESCENDING)])
            db.sc_price_observations.create_index("observation_id", unique=True)
            db.sc_price_observations.create_index([("product_id", ASCENDING), ("observed_at", DESCENDING)])
            db.sc_price_daily.create_index([("product_id", ASCENDING), ("date", DESCENDING)])
            db.sc_product_quarantine.create_index([("domain", ASCENDING), ("created_at", DESCENDING)])
            db.sc_synthetic_products.create_index("synthetic_id", unique=True)
            db.sc_synthetic_products.create_index([("source_id", ASCENDING), ("created_at", DESCENDING)])
            db.sc_synthetic_products.create_index([("batch_id", ASCENDING), ("review_status", ASCENDING)])
            db.sc_synthetic_quarantine.create_index("synthetic_id", unique=True)
            db.sc_synthetic_quarantine.create_index([("source_id", ASCENDING), ("created_at", DESCENDING)])
            self._indexes_ready = True
            self._index_error = None
            return True
        except PyMongoError as exc:
            log.error("Admin Center Mongo index initialization failed: %s", exc)
            self._index_error = str(exc)
            return False

    def close(self) -> None:
        with self._state_lock:
            client = self.client
            self.client = None
            self._db = None
            self._indexes_ready = False
        if client is not None:
            client.close()

    def ready(self) -> bool:
        db = self.get_db()
        if db is None:
            return False
        try:
            db.command("ping")
            self.ensure_indexes()
            return True
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
            "store_scope": source.get("store_scope") or "site",
            "store_name": source.get("store_name"),
            "store_url": source.get("store_url"),
            "store_address": source.get("store_address"),
            "store_phone": source.get("store_phone"),
            "store_channel": source.get("store_channel"),
            "auto_promote_rules": source.get("auto_promote_rules", True),
            "quality_gate_enabled": source.get("quality_gate_enabled", True),
            "important": source.get("important", False),
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
            "store_scope": doc.get("store_scope") or "site",
            "store_name": doc.get("store_name"),
            "store_url": doc.get("store_url"),
            "store_address": doc.get("store_address"),
            "store_phone": doc.get("store_phone"),
            "store_channel": doc.get("store_channel"),
            "auto_promote_rules": doc.get("auto_promote_rules", True),
            "quality_gate_enabled": doc.get("quality_gate_enabled", True),
            "important": doc.get("important", False),
        }

    # Products and market views

    # Extraction rules

    def seed_rule_structures(self, structures: list[dict[str, Any]]) -> int:
        db = self.get_db()
        if db is None:
            return 0
        try:
            if db.admin_extraction_rules.count_documents({}, limit=1):
                return 0
        except PyMongoError as exc:
            log.warning("Admin Center extraction rule seed skipped; rules collection is not readable: %s", exc)
            return 0

        inserted = 0
        for structure in structures:
            domain = str(structure.get("domain") or "").strip().lower()
            if not domain:
                continue
            try:
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
            except PyMongoError as exc:
                log.warning("Admin Center extraction rule seed skipped for %s: %s", domain, exc)
                break
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
        if current and current.get("version") != version:
            db.admin_extraction_rule_versions.insert_one({
                "domain": domain,
                "structure": current.get("structure"),
                "version": current.get("version"),
                "quality": current.get("quality"),
                "status": "retired",
                "created_at": now_utc(),
            })
        db.admin_extraction_rules.update_one(
            {"domain": domain},
            {
                "$set": {"structure": structure, "version": version, "updated_at": now_utc()},
                "$setOnInsert": {"domain": domain, "created_at": now_utc()},
            },
            upsert=True,
        )
        return {"domain": domain, "structure": structure, "version": version}

    def save_rule_candidate(
        self,
        domain: str,
        structure: dict[str, Any],
        validation: dict[str, Any],
        *,
        model: str | None,
        artifact_ids: list[str],
        content_hash: str | None = None,
    ) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        version = self.rule_version(structure)
        candidate_id = f"{domain}:{content_hash}:{version}" if content_hash else f"{domain}:{version}"
        payload = {
            "candidate_id": candidate_id,
            "domain": domain,
            "structure": structure,
            "version": version,
            "status": "validated" if validation.get("accepted") else "rejected",
            "quality": validation,
            "score": float(validation.get("score") or 0),
            "model": model,
            "artifact_ids": artifact_ids,
            "content_hash": content_hash,
            "updated_at": now_utc(),
        }
        db.admin_extraction_rule_candidates.update_one(
            {"candidate_id": candidate_id},
            {"$set": payload, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True,
        )
        return payload

    def cached_rule_candidate(
        self,
        domain: str,
        content_hash: str,
        *,
        model: str | None = None,
        rejected_ttl_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None or not content_hash:
            return None
        query: dict[str, Any] = {"domain": domain, "content_hash": content_hash}
        if model:
            query["model"] = model
        if rejected_ttl_seconds is not None:
            cutoff = now_utc() - timedelta(seconds=max(0, rejected_ttl_seconds))
            query["$or"] = [
                {"status": {"$ne": "rejected"}},
                {"updated_at": {"$gte": cutoff}},
            ]
        return db.admin_extraction_rule_candidates.find_one(
            query,
            {"_id": False},
            sort=[("updated_at", DESCENDING)],
        )

    def rule_generation_attempt(
        self,
        domain: str,
        content_hash: str,
        *,
        model: str | None = None,
    ) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None or not content_hash:
            return None
        query: dict[str, Any] = {"domain": domain, "content_hash": content_hash}
        if model:
            query["model"] = model
        return db.admin_rule_generation_attempts.find_one(
            query,
            {"_id": False},
        )

    def record_rule_generation_attempt(
        self,
        domain: str,
        content_hash: str,
        *,
        status: str,
        model: str | None = None,
        error: str | None = None,
        cooldown_seconds: int = 0,
    ) -> None:
        db = self.get_db()
        if db is None or not content_hash:
            return
        now = now_utc()
        db.admin_rule_generation_attempts.update_one(
            {"domain": domain, "content_hash": content_hash},
            {
                "$set": {
                    "domain": domain,
                    "content_hash": content_hash,
                    "status": status,
                    "model": model,
                    "error": error,
                    "retry_after": now + timedelta(seconds=max(0, cooldown_seconds)) if cooldown_seconds else None,
                    "updated_at": now,
                },
                "$inc": {"attempt_count": 1},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def promote_rule_candidate(self, candidate_id: str, expected_version: str | None = None) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        candidate = db.admin_extraction_rule_candidates.find_one({"candidate_id": candidate_id}, {"_id": False})
        if not candidate or candidate.get("status") != "validated":
            return None
        domain = candidate["domain"]
        current = db.admin_extraction_rules.find_one({"domain": domain}, {"_id": False})
        if expected_version and current and current.get("version") != expected_version:
            return {"conflict": True, "version": current.get("version")}
        current_score = float(((current or {}).get("quality") or {}).get("score") or 0)
        candidate_score = float(candidate.get("score") or 0)
        if current and current_score > candidate_score:
            return {"promoted": False, "reason": "candidate_score_lower", "version": current.get("version")}
        if current:
            db.admin_extraction_rule_versions.insert_one({
                "domain": domain,
                "structure": current.get("structure"),
                "version": current.get("version"),
                "quality": current.get("quality"),
                "status": "retired",
                "created_at": now_utc(),
            })
        db.admin_extraction_rules.update_one(
            {"domain": domain},
            {
                "$set": {
                    "structure": candidate["structure"],
                    "version": candidate["version"],
                    "quality": candidate.get("quality"),
                    "candidate_id": candidate_id,
                    "updated_at": now_utc(),
                },
                "$setOnInsert": {"domain": domain, "created_at": now_utc()},
            },
            upsert=True,
        )
        db.admin_extraction_rule_candidates.update_one(
            {"candidate_id": candidate_id},
            {"$set": {"status": "promoted", "promoted_at": now_utc()}},
        )
        return {
            "domain": domain,
            "structure": candidate["structure"],
            "version": candidate["version"],
            "quality": candidate.get("quality"),
            "promoted": True,
        }

    def rule_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        return db.admin_extraction_rule_candidates.find_one({"candidate_id": candidate_id}, {"_id": False})

    def list_rule_candidates(self, domain: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        query: dict[str, Any] = {}
        if domain:
            query["domain"] = domain
        if status and status != "all":
            query["status"] = status
        return list(db.admin_extraction_rule_candidates.find(query, {"_id": False}).sort("updated_at", DESCENDING).limit(limit))

    def rollback_rule(self, domain: str, version: str | None = None) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        query: dict[str, Any] = {"domain": domain}
        if version:
            query["version"] = version
        previous = db.admin_extraction_rule_versions.find_one(query, {"_id": False}, sort=[("created_at", DESCENDING)])
        if not previous:
            return None
        current = db.admin_extraction_rules.find_one({"domain": domain}, {"_id": False})
        if current:
            db.admin_extraction_rule_versions.insert_one({
                "domain": domain,
                "structure": current.get("structure"),
                "version": current.get("version"),
                "quality": current.get("quality"),
                "status": "rolled_back",
                "created_at": now_utc(),
            })
        db.admin_extraction_rules.update_one(
            {"domain": domain},
            {"$set": {
                "structure": previous.get("structure"),
                "version": previous.get("version"),
                "quality": previous.get("quality"),
                "updated_at": now_utc(),
            }},
            upsert=True,
        )
        return {"domain": domain, "version": previous.get("version"), "structure": previous.get("structure")}

    def acquire_pipeline_lease(self, pipeline_id: str, run_id: str, lease_seconds: int = 900) -> bool:
        db = self.get_db()
        if db is None:
            return False
        now = now_utc()
        locked = db.admin_pipelines.find_one_and_update(
            {
                "pipeline_id": pipeline_id,
                "$or": [
                    {"locked_until": {"$exists": False}},
                    {"locked_until": {"$lte": now}},
                    {"locked_by_run_id": run_id},
                ],
            },
            {"$set": {"locked_until": now + timedelta(seconds=lease_seconds), "locked_by_run_id": run_id}},
            return_document=ReturnDocument.AFTER,
        )
        return locked is not None

    def release_pipeline_lease(self, pipeline_id: str, run_id: str) -> None:
        db = self.get_db()
        if db is not None:
            db.admin_pipelines.update_one(
                {"pipeline_id": pipeline_id, "locked_by_run_id": run_id},
                {"$unset": {"locked_until": "", "locked_by_run_id": ""}},
            )

    def renew_pipeline_lease(self, pipeline_id: str, run_id: str, lease_seconds: int) -> bool:
        db = self.get_db()
        if db is None:
            return False
        result = db.admin_pipelines.update_one(
            {"pipeline_id": pipeline_id, "locked_by_run_id": run_id},
            {"$set": {"locked_until": now_utc() + timedelta(seconds=lease_seconds)}},
        )
        return bool(result.matched_count)

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
                    {"store_name": store_expr},
                    {"store_url": store_expr},
                    {"store_address": store_expr},
                    {"store_phone": store_expr},
                    {"raw_data.store_name": store_expr},
                    {"raw_data.store_url": store_expr},
                    {"raw_data.store_address": store_expr},
                    {"raw_data.store_phone": store_expr},
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
        price = doc.get("price_numeric")
        if price is None:
            price = doc.get("price")
        price_numeric = self._normalize_price(price)
        raw_data = doc.get("raw_data") or {}
        product_url = doc.get("product_url") or doc.get("url")
        name = doc.get("product_name") or doc.get("name") or doc.get("canonical_name")
        if self._is_url_like(name):
            product_url = product_url or name
            name = self._name_from_url(name)
        if not name and product_url:
            name = self._name_from_url(product_url)
        category = self._normalize_category(doc.get("category") or doc.get("normalized_category"), name, product_url, doc.get("domain"))
        return {
            "name": name,
            "price": price_numeric,
            "price_numeric": price_numeric,
            "price_status": doc.get("price_status") or ("FOUND" if price_numeric and price_numeric > 0 else "MISSING"),
            "original_price": doc.get("old_price") or doc.get("original_price"),
            "currency": doc.get("currency", "VND"),
            "url": product_url,
            "source": doc.get("domain") or doc.get("source_site"),
            "source_site": doc.get("domain") or doc.get("source_site"),
            "category": category,
            "image": doc.get("image_url"),
            "image_url": doc.get("image_url"),
            "brand": doc.get("brand"),
            "store_name": doc.get("store_name") or raw_data.get("store_name") or "",
            "store_url": doc.get("store_url") or raw_data.get("store_url") or "",
            "store_address": doc.get("store_address") or raw_data.get("store_address"),
            "store_channel": doc.get("store_channel") or raw_data.get("store_channel"),
            "address_status": doc.get("address_status") or raw_data.get("address_status") or "MISSING",
            "store_phone": doc.get("store_phone") or raw_data.get("store_phone") or "",
            "data_origin": doc.get("data_origin"),
            "rule_version": doc.get("rule_version"),
            "extraction_method": doc.get("extraction_method"),
            "validation_score": doc.get("validation_score"),
            "updated_at": doc.get("updated_at") or doc.get("created_at"),
        }

    @staticmethod
    def _normalize_price(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value) if float(value) > 0 else None
        text = " ".join(str(value or "").split())
        if not text:
            return None
        match = re.search(r"\d[\d.,\s]*", text)
        digits = re.sub(r"[^\d]", "", match.group(0) if match else text)
        if not digits:
            return None
        try:
            parsed = float(digits)
        except ValueError:
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _is_url_like(value: Any) -> bool:
        return bool(URL_RE.match(" ".join(str(value or "").split())))

    @staticmethod
    def _name_from_url(value: Any) -> str:
        text = " ".join(str(value or "").split())
        path = re.sub(r"[?#].*$", "", text).rstrip("/").split("/")[-1]
        path = re.sub(r"\.(html?|php|aspx?)$", "", path, flags=re.IGNORECASE)
        path = re.sub(r"[-_]+", " ", path)
        path = re.sub(r"\b(sp|sku|id|vk)\d+\b", "", path, flags=re.IGNORECASE)
        return " ".join(path.split()).title()

    @staticmethod
    def _normalize_category(*values: Any) -> str:
        haystack = " ".join(" ".join(str(value or "").lower().split()) for value in values if value)
        if any(keyword in haystack for keyword in ("ruou", "rượu", "vodka", "whisky", "whiskey", "wine", "soju", "cognac", "rum", "gin", "tequila", "brandy", "liqueur")):
            return "Rượu"
        if any(keyword in haystack for keyword in ("bia", "beer", "lager", "ale", "stout")):
            return "Bia"
        if any(keyword in haystack for keyword in ("thuoc la", "thuốc lá", "cigarette", "cigar", "tobacco")):
            return "Thuốc lá"
        if any(keyword in haystack for keyword in ("sua", "sữa", "milk", "vinamilk", "th true milk", "moc chau milk", "dutch lady")):
            return "Sữa"
        return "Khác"

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

    def source_product_counts(self, domains: list[str]) -> dict[str, dict[str, int]]:
        """Return persisted and quarantined product counts grouped by domain."""
        db = self.get_db()
        if db is None or not domains:
            return {}
        aliases = set(domains)
        for domain in domains:
            aliases.add(domain.removeprefix("www."))
            if not domain.startswith("www."):
                aliases.add(f"www.{domain}")

        counts: dict[str, dict[str, int]] = {}
        for field, collection in (
            ("products", db.sc_products),
            ("quarantined", db.sc_product_quarantine),
        ):
            rows = collection.aggregate([
                {"$match": {"domain": {"$in": list(aliases)}}},
                {"$group": {"_id": "$domain", "count": {"$sum": 1}}},
            ])
            for row in rows:
                domain = str(row.get("_id") or "")
                if domain:
                    counts.setdefault(domain, {"products": 0, "quarantined": 0})[field] = int(row.get("count") or 0)
        return counts

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
        # New approach: read from local store
        raw_page_id = doc.get("raw_page_id")
        if not raw_page_id:
            return None
        local_raw_dir = Path(__file__).resolve().parents[4] / "store" / "raw"
        content_type = doc.get("content_type", "mhtml")
        filename = doc.get("metadata", {}).get("filename") or f"{raw_page_id}.{content_type}"
        file_path = local_raw_dir / filename
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    return handle.read()
            except Exception as exc:
                log.warning("Could not read local raw page %s: %s", raw_page_id, exc)
                return None
                
        # Legacy fallback
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
            
        # New approach: write to local store
        local_raw_dir = Path(__file__).resolve().parents[4] / "store" / "raw"
        local_raw_dir.mkdir(parents=True, exist_ok=True)
        filename = payload.get("metadata", {}).get("filename") or f"{payload['raw_page_id']}.{payload['content_type']}"
        file_path = local_raw_dir / filename
        try:
            with open(file_path, "wb") as handle:
                handle.write(content)
            # Also write metadata
            with open(local_raw_dir / f"{payload['raw_page_id']}.meta.json", "w", encoding="utf-8") as handle:
                json.dump(payload, handle, default=str)
        except Exception as exc:
            log.warning("Could not write local raw page %s: %s", payload["raw_page_id"], exc)

        db.sc_raw_pages.update_one(
            {"raw_page_id": payload["raw_page_id"]},
            {"$set": payload, "$setOnInsert": {"created_at": now_utc()}},
            upsert=True,
        )
        self.prune_raw_pages(payload["domain"])
        return payload

    def prune_raw_pages(self, domain: str | None = None) -> int:
        """Trim raw HTML/GridFS artifacts so Atlas storage stays bounded."""
        db = self.get_db()
        if db is None:
            return 0
        retention_days = self._env_int("WORKER_RAW_PAGE_RETENTION_DAYS", 14)
        max_per_domain = self._env_int("WORKER_MAX_RAW_PAGES_PER_DOMAIN", 100)
        fs = GridFS(db)
        removed = 0

        cutoff = now_utc() - timedelta(days=max(1, retention_days))
        old_query: dict[str, Any] = {"captured_at": {"$lt": cutoff}}
        if domain:
            old_query["domain"] = domain
        removed += self._delete_raw_page_docs(db, fs, old_query)

        if max_per_domain > 0:
            domains = [domain] if domain else [value for value in db.sc_raw_pages.distinct("domain") if value]
            for item in domains:
                keep = list(
                    db.sc_raw_pages.find({"domain": item}, {"_id": False, "raw_page_id": True})
                    .sort("captured_at", DESCENDING)
                    .limit(max_per_domain)
                )
                keep_ids = [row.get("raw_page_id") for row in keep if row.get("raw_page_id")]
                overflow_query: dict[str, Any] = {"domain": item}
                if keep_ids:
                    overflow_query["raw_page_id"] = {"$nin": keep_ids}
                removed += self._delete_raw_page_docs(db, fs, overflow_query)
        return removed

    def _delete_raw_page_docs(self, db: Database, fs: GridFS, query: dict[str, Any]) -> int:
        docs = list(db.sc_raw_pages.find(query, {"_id": False, "raw_page_id": True, "gridfs_file_id": True}))
        if not docs:
            return 0
        local_raw_dir = Path(__file__).resolve().parents[4] / "store" / "raw"
        for doc in docs:
            if doc.get("gridfs_file_id"):
                self._delete_gridfs_file(fs, doc.get("gridfs_file_id"))
            raw_page_id = doc.get("raw_page_id")
            if raw_page_id:
                # delete local files
                for f in local_raw_dir.glob(f"{raw_page_id}.*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
        ids = [doc.get("raw_page_id") for doc in docs if doc.get("raw_page_id")]
        if ids:
            db.sc_raw_pages.delete_many({"raw_page_id": {"$in": ids}})
        return len(docs)

    @staticmethod
    def _delete_gridfs_file(fs: GridFS, file_id: Any) -> None:
        try:
            fs.delete(file_id)
        except Exception as exc:
            log.warning("Could not delete GridFS file %s during raw page cleanup: %s", file_id, exc)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

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

    def get_latest_prompt(self, key: str) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        doc = db.sc_generation_prompts.find_one({"key": key}, sort=[("version", DESCENDING)])
        if doc:
            doc.pop("_id", None)
        return doc

    def save_new_prompt_version(self, key: str, content: str) -> dict[str, Any] | None:
        db = self.get_db()
        if db is None:
            return None
        latest = self.get_latest_prompt(key)
        new_version = (latest["version"] + 1) if latest else 1
        doc = {
            "key": key,
            "version": new_version,
            "content": content,
            "created_at": now_utc()
        }
        db.sc_generation_prompts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    def list_prompt_versions(self, key: str) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is None:
            return []
        cursor = db.sc_generation_prompts.find({"key": key}, {"_id": False}).sort("version", DESCENDING)
        return list(cursor)
