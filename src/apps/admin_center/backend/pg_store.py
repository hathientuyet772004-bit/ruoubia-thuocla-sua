"""PostgreSQL data store for Admin Center."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import Any, Callable, TypeVar

import psycopg2
import psycopg2.extras
import psycopg2.pool

from apps.admin_center.backend.settings import settings

log = logging.getLogger("admin_center.pg_store")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
T = TypeVar("T")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _j(obj: Any) -> psycopg2.extras.Json:
    return psycopg2.extras.Json(obj, dumps=lambda v: json.dumps(v, default=_json_default))


class AdminPgStore:
    """PostgreSQL access layer for Admin Center."""

    _STATIC_CATEGORY_RULES: list[tuple[str, list[str]]] = [
        ("Rượu",    ["ruou","rượu","vodka","whisky","whiskey","wine","soju","cognac","rum","gin","tequila","brandy","liqueur"]),
        ("Bia",     ["bia","beer","lager","ale","stout"]),
        ("Thuốc lá", ["thuoc la","thuốc lá","cigarette","cigar","tobacco"]),
        ("Sữa",    ["sua","sữa","milk","vinamilk","th true milk","moc chau milk","dutch lady"]),
    ]

    def __init__(self) -> None:
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None
        self._pool_error: str | None = None
        self._unavailable_until = 0.0
        self._lock = RLock()
        self._category_rules_cache: list[tuple[str, list[str]]] | None = None
        self._category_rules_loaded_at: float = 0.0
        self._source_schema_ready = False
        self._store_schema_ready = False

    # ── Connection pool ─────────────────────────────────────────────────────

    def _get_pool(self) -> psycopg2.pool.ThreadedConnectionPool | None:
        with self._lock:
            if self._pool is not None:
                return self._pool
            if time.monotonic() < self._unavailable_until:
                return None
        db_url = settings.DATABASE_URL or os.environ.get("DATABASE_URL") or settings.PG_URL
        if not db_url:
            log.warning("DATABASE_URL / PG_URL not set; PostgreSQL store unavailable.")
            return None
        try:
            pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=10,
                dsn=db_url,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            with self._lock:
                self._pool = pool
                self._pool_error = None
            return pool
        except Exception as exc:
            log.error("PgStore connection pool init failed: %s", exc)
            with self._lock:
                self._pool_error = str(exc)
                self._unavailable_until = time.monotonic() + 30
            return None

    @contextmanager
    def _conn(self):
        pool = self._get_pool()
        if pool is None:
            yield None
            return
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                pool.putconn(conn)
            except Exception:
                pass

    def read_or_default(self, operation: str, loader: Callable[[], T], default: T) -> T:
        try:
            return loader()
        except Exception as exc:
            log.warning("PgStore read failed for %s: %s", operation, exc)
            return default

    def mark_read_unavailable(self, error: object, cooldown_seconds: int = 30) -> None:
        with self._lock:
            self._unavailable_until = time.monotonic() + max(1, cooldown_seconds)
        log.warning("PgStore paused for %ss: %s", cooldown_seconds, error)

    def connection_status(self) -> dict[str, Any]:
        pool = self._get_pool()
        db_available = pool is not None
        return {
            "db_available": db_available,
            "data_status": "ok" if db_available else "degraded",
            "connecting": False,
            "cooldown_active": time.monotonic() < self._unavailable_until,
            "indexes_ready": db_available,
            "index_status": "ready" if db_available else "degraded",
            "detail": self._pool_error if not db_available else None,
        }

    def get_db(self):
        """Return a small collection-style adapter backed by PostgreSQL."""
        if self._get_pool() is None:
            return None
        self.ensure_store_location_table()
        return _PgCompatDb(self)

    def ready(self) -> bool:
        with self._conn() as conn:
            if conn is None:
                return False
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            except Exception as exc:
                log.error("PgStore readiness check failed: %s", exc)
                return False

    def close(self) -> None:
        with self._lock:
            pool = self._pool
            self._pool = None
        if pool:
            try:
                pool.closeall()
            except Exception:
                pass

    # ── Source registry ──────────────────────────────────────────────────────

    def ensure_source_store_columns(self) -> None:
        if self._source_schema_ready:
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE sources ADD COLUMN IF NOT EXISTS store_locator_url TEXT")
                cur.execute("ALTER TABLE sources ALTER COLUMN store_channel SET DEFAULT 'online'")
        self._source_schema_ready = True

    def ensure_store_location_table(self) -> None:
        if self._store_schema_ready:
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sc_store_locations (
                        store_location_id TEXT PRIMARY KEY,
                        source_id TEXT,
                        domain TEXT,
                        store_name TEXT,
                        store_address TEXT,
                        address_status TEXT,
                        store_channel TEXT,
                        store_phone TEXT,
                        store_url TEXT,
                        raw_page_id TEXT,
                        raw_data JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
        self._store_schema_ready = True

    def seed_sources(self, rows: list[dict[str, Any]]) -> int:
        with self._conn() as conn:
            if conn is None:
                return 0
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM sources")
                if (cur.fetchone() or {}).get("n", 0) > 0:
                    return 0
        inserted = 0
        for row in rows:
            if row.get("name") and row.get("url"):
                if self.create_source(row):
                    inserted += 1
        return inserted

    def list_sources(self, limit: int = 500) -> list[dict[str, Any]]:
        self.ensure_source_store_columns()
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM sources ORDER BY updated_at DESC LIMIT %s", (limit,)
                )
                return [self._source_view(dict(r)) for r in cur.fetchall()]

    def create_source(self, source: dict[str, Any]) -> dict[str, Any] | None:
        payload = self._source_payload(source)
        self.ensure_source_store_columns()
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sources (source_id,name,url,base_url,domain,type,category,
                      target_categories,note,store_scope,store_name,store_url,store_address,
                      store_phone,store_channel,store_locator_url,auto_promote_rules,quality_gate_enabled,
                      important,enabled,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (source_id) DO NOTHING
                """, (
                    payload["source_id"], payload["name"], payload["url"], payload["base_url"],
                    payload["domain"], payload["type"], payload["category"],
                    _j(payload["target_categories"]), payload["note"], payload["store_scope"],
                    payload["store_name"], payload["store_url"], payload["store_address"],
                    payload["store_phone"], payload["store_channel"], payload["store_locator_url"],
                    payload["auto_promote_rules"], payload["quality_gate_enabled"],
                    payload["important"], payload["enabled"],
                    payload["created_at"], payload["updated_at"],
                ))
        return self._source_view(payload)

    def update_source(self, source_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        self.ensure_source_store_columns()
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sources WHERE source_id = %s", (source_id,))
                current = cur.fetchone()
                if current is None:
                    return None
                merged = {**dict(current), **updates, "source_id": source_id}
                payload = self._source_payload(merged)
                cur.execute("""
                    UPDATE sources SET name=%s,url=%s,base_url=%s,domain=%s,type=%s,category=%s,
                      target_categories=%s,note=%s,store_scope=%s,store_name=%s,store_url=%s,
                      store_address=%s,store_phone=%s,store_channel=%s,store_locator_url=%s,auto_promote_rules=%s,
                      quality_gate_enabled=%s,important=%s,enabled=%s,updated_at=%s
                    WHERE source_id=%s
                """, (
                    payload["name"], payload["url"], payload["base_url"], payload["domain"],
                    payload["type"], payload["category"], _j(payload["target_categories"]),
                    payload["note"], payload["store_scope"], payload["store_name"],
                    payload["store_url"], payload["store_address"], payload["store_phone"],
                    payload["store_channel"], payload["store_locator_url"], payload["auto_promote_rules"],
                    payload["quality_gate_enabled"], payload["important"], payload["enabled"],
                    payload["updated_at"], source_id,
                ))
                self._apply_site_store_config(cur, source_id, payload)
        return self._source_view(payload)

    def _apply_site_store_config(self, cur: Any, source_id: str, payload: dict[str, Any]) -> None:
        if str(payload.get("store_scope") or "site").lower() != "site":
            return
        if not any(payload.get(key) for key in ("store_name", "store_url", "store_address", "store_phone", "store_channel")):
            return
        status = "FOUND" if payload.get("store_address") else ("NOT_APPLICABLE" if payload.get("store_channel") == "online" else "MISSING")
        params = (
            payload.get("store_name"), payload.get("store_url"), payload.get("store_address"),
            payload.get("store_phone"), payload.get("store_channel"), status, now_utc(), source_id,
        )
        cur.execute("""
            UPDATE sc_products
            SET store_name=%s, store_url=%s, store_address=%s, store_phone=%s,
                store_channel=%s, address_status=%s, updated_at=%s
            WHERE source_id=%s
        """, params)
        cur.execute("""
            UPDATE sc_offers
            SET store_name=%s, store_url=%s, store_address=%s, store_phone=%s,
                updated_at=%s
            WHERE source_id=%s
        """, (
            payload.get("store_name"), payload.get("store_url"), payload.get("store_address"),
            payload.get("store_phone"), now_utc(), source_id,
        ))

    def delete_source(self, source_id: str) -> bool:
        with self._conn() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sources WHERE source_id = %s", (source_id,))
                return cur.rowcount > 0

    def _source_payload(self, source: dict[str, Any]) -> dict[str, Any]:
        from urllib.parse import urlparse
        url = source.get("url") or source.get("base_url") or ""
        domain = source.get("domain") or urlparse(url).netloc
        return {
            "source_id": str(source.get("source_id") or source.get("id") or uuid.uuid4()),
            "name": source.get("name"),
            "url": url, "base_url": url, "domain": domain,
            "type": source.get("type") or source.get("source_type") or "Website",
            "category": source.get("category") or ", ".join(source.get("target_categories", [])),
            "target_categories": source.get("target_categories", []),
            "note": source.get("note") or source.get("notes"),
            "store_scope": source.get("store_scope") or "site",
            "store_name": source.get("store_name"),
            "store_url": source.get("store_url"),
            "store_address": source.get("store_address"),
            "store_phone": source.get("store_phone"),
            "store_channel": source.get("store_channel") or "online",
            "store_locator_url": source.get("store_locator_url"),
            "auto_promote_rules": source.get("auto_promote_rules", True),
            "quality_gate_enabled": source.get("quality_gate_enabled", True),
            "important": source.get("important", False),
            "enabled": source.get("enabled", True),
            "created_at": source.get("created_at") or now_utc(),
            "updated_at": now_utc(),
        }

    def _source_view(self, doc: dict[str, Any]) -> dict[str, Any]:
        cats = doc.get("target_categories") or []
        if isinstance(cats, str):
            try:
                cats = json.loads(cats)
            except Exception:
                cats = []
        return {
            "id": str(doc.get("source_id") or doc.get("id")),
            "name": doc.get("name"),
            "url": doc.get("url") or doc.get("base_url"),
            "type": doc.get("type") or doc.get("source_type"),
            "category": doc.get("category") or ", ".join(cats),
            "note": doc.get("note"),
            "domain": doc.get("domain"),
            "store_scope": doc.get("store_scope") or "site",
            "store_name": doc.get("store_name"),
            "store_url": doc.get("store_url"),
            "store_address": doc.get("store_address"),
            "store_phone": doc.get("store_phone"),
            "store_channel": doc.get("store_channel") or "online",
            "store_locator_url": doc.get("store_locator_url"),
            "auto_promote_rules": doc.get("auto_promote_rules", True),
            "quality_gate_enabled": doc.get("quality_gate_enabled", True),
            "important": doc.get("important", False),
        }

    # ── Extraction rules ─────────────────────────────────────────────────────

    def seed_rule_structures(self, structures: list[dict[str, Any]]) -> int:
        with self._conn() as conn:
            if conn is None:
                return 0
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM admin_extraction_rules")
                if (cur.fetchone() or {}).get("n", 0) > 0:
                    return 0
        inserted = 0
        for structure in structures:
            domain = str(structure.get("domain") or "").strip().lower()
            if not domain:
                continue
            version = self.rule_version(structure)
            with self._conn() as conn:
                if conn is None:
                    break
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO admin_extraction_rules (domain,structure,version,created_at,updated_at)
                        VALUES (%s,%s,%s,%s,%s) ON CONFLICT (domain) DO NOTHING
                    """, (domain, _j(structure), version, now_utc(), now_utc()))
                    if cur.rowcount:
                        inserted += 1
        return inserted

    def list_rule_structures(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute("SELECT domain,structure,version,quality,candidate_id,created_at,updated_at FROM admin_extraction_rules ORDER BY updated_at DESC")
                return [self._rule_row(dict(r)) for r in cur.fetchall()]

    def rule_structure(self, domain: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_extraction_rules WHERE domain=%s", (domain,))
                row = cur.fetchone()
                return self._rule_row(dict(row)) if row else None

    def save_rule_structure(self, domain: str, structure: dict[str, Any], expected_version: str | None) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_extraction_rules WHERE domain=%s", (domain,))
                current = cur.fetchone()
                current = dict(current) if current else None
                if current is None and expected_version:
                    return None
                if expected_version and current and current.get("version") != expected_version:
                    return {"conflict": True, "version": current.get("version")}
                version = self.rule_version(structure)
                if current and current.get("version") != version:
                    cur.execute("""
                        INSERT INTO admin_extraction_rule_versions (domain,structure,version,quality,status,created_at)
                        VALUES (%s,%s,%s,%s,'retired',%s)
                    """, (domain, _j(current.get("structure") or {}), current.get("version"), _j(current.get("quality")), now_utc()))
                cur.execute("""
                    INSERT INTO admin_extraction_rules (domain,structure,version,updated_at,created_at)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (domain) DO UPDATE
                    SET structure=EXCLUDED.structure, version=EXCLUDED.version, updated_at=EXCLUDED.updated_at
                """, (domain, _j(structure), version, now_utc(), now_utc()))
        return {"domain": domain, "structure": structure, "version": version}

    def save_rule_candidate(self, domain: str, structure: dict[str, Any], validation: dict[str, Any], *, model: str | None, artifact_ids: list[str], content_hash: str | None = None) -> dict[str, Any] | None:
        version = self.rule_version(structure)
        candidate_id = f"{domain}:{content_hash}:{version}" if content_hash else f"{domain}:{version}"
        payload = {
            "candidate_id": candidate_id, "domain": domain, "structure": structure,
            "version": version, "status": "validated" if validation.get("accepted") else "rejected",
            "quality": validation, "score": float(validation.get("score") or 0),
            "model": model, "artifact_ids": artifact_ids, "content_hash": content_hash,
        }
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_extraction_rule_candidates
                      (candidate_id,domain,structure,version,status,quality,score,model,artifact_ids,content_hash,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (candidate_id) DO UPDATE
                    SET structure=EXCLUDED.structure,version=EXCLUDED.version,status=EXCLUDED.status,
                        quality=EXCLUDED.quality,score=EXCLUDED.score,updated_at=EXCLUDED.updated_at
                """, (candidate_id, domain, _j(structure), version, payload["status"],
                      _j(validation), payload["score"], model, _j(artifact_ids),
                      content_hash, now_utc(), now_utc()))
        return payload

    def cached_rule_candidate(self, domain: str, content_hash: str, *, model: str | None = None, rejected_ttl_seconds: int | None = None) -> dict[str, Any] | None:
        if not content_hash:
            return None
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_extraction_rule_candidates"):
            query: dict[str, Any] = {"domain": domain, "content_hash": content_hash}
            if model:
                query["model"] = model
            if rejected_ttl_seconds is not None:
                cutoff = now_utc() - timedelta(seconds=max(0, rejected_ttl_seconds))
                query["$or"] = [{"status": {"$ne": "rejected"}}, {"updated_at": {"$gte": cutoff}}]
            doc = db.admin_extraction_rule_candidates.find_one(query, {"_id": False})
            return self._rule_candidate_row(dict(doc)) if isinstance(doc, dict) else None
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                params: list[Any] = [domain, content_hash]
                model_clause = "AND model=%s" if model else ""
                if model:
                    params.append(model)
                ttl_clause = ""
                if rejected_ttl_seconds is not None:
                    cutoff = now_utc() - timedelta(seconds=max(0, rejected_ttl_seconds))
                    ttl_clause = "AND (status != 'rejected' OR updated_at >= %s)"
                    params.append(cutoff)
                cur.execute(f"""
                    SELECT * FROM admin_extraction_rule_candidates
                    WHERE domain=%s AND content_hash=%s {model_clause} {ttl_clause}
                    ORDER BY updated_at DESC LIMIT 1
                """, params)
                row = cur.fetchone()
                return self._rule_candidate_row(dict(row)) if row else None

    def rule_generation_attempt(self, domain: str, content_hash: str, *, model: str | None = None) -> dict[str, Any] | None:
        if not content_hash:
            return None
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                params: list[Any] = [domain, content_hash]
                model_clause = "AND model=%s" if model else ""
                if model:
                    params.append(model)
                cur.execute(f"SELECT * FROM admin_rule_generation_attempts WHERE domain=%s AND content_hash=%s {model_clause}", params)
                row = cur.fetchone()
                return dict(row) if row else None

    def record_rule_generation_attempt(self, domain: str, content_hash: str, *, status: str, model: str | None = None, error: str | None = None, cooldown_seconds: int = 0) -> None:
        if not content_hash:
            return
        retry_after = now_utc() + timedelta(seconds=max(0, cooldown_seconds)) if cooldown_seconds else None
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_rule_generation_attempts (domain,content_hash,status,model,error,retry_after,attempt_count,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s)
                    ON CONFLICT (domain,content_hash) DO UPDATE
                    SET status=EXCLUDED.status,model=EXCLUDED.model,error=EXCLUDED.error,
                        retry_after=EXCLUDED.retry_after,attempt_count=admin_rule_generation_attempts.attempt_count+1,
                        updated_at=EXCLUDED.updated_at
                """, (domain, content_hash, status, model, error, retry_after, now_utc(), now_utc()))

    def promote_rule_candidate(self, candidate_id: str, expected_version: str | None = None) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_extraction_rule_candidates WHERE candidate_id=%s", (candidate_id,))
                candidate = cur.fetchone()
                if not candidate or candidate.get("status") != "validated":
                    return None
                candidate = dict(candidate)
                domain = candidate["domain"]
                cur.execute("SELECT * FROM admin_extraction_rules WHERE domain=%s", (domain,))
                current = cur.fetchone()
                current = dict(current) if current else None
                if expected_version and current and current.get("version") != expected_version:
                    return {"conflict": True, "version": current.get("version")}
                current_score = float(((current or {}).get("quality") or {}).get("score") or 0) if current else 0
                candidate_score = float(candidate.get("score") or 0)
                if current and current_score > candidate_score:
                    return {"promoted": False, "reason": "candidate_score_lower", "version": current.get("version")}
                if current:
                    cur.execute("""
                        INSERT INTO admin_extraction_rule_versions (domain,structure,version,quality,status,created_at)
                        VALUES (%s,%s,%s,%s,'retired',%s)
                    """, (domain, _j(current.get("structure") or {}), current.get("version"), _j(current.get("quality")), now_utc()))
                cur.execute("""
                    INSERT INTO admin_extraction_rules (domain,structure,version,quality,candidate_id,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (domain) DO UPDATE
                    SET structure=EXCLUDED.structure,version=EXCLUDED.version,
                        quality=EXCLUDED.quality,candidate_id=EXCLUDED.candidate_id,updated_at=EXCLUDED.updated_at
                """, (domain, _j(candidate["structure"]), candidate["version"],
                      _j(candidate.get("quality")), candidate_id, now_utc(), now_utc()))
                cur.execute("UPDATE admin_extraction_rule_candidates SET status='promoted',updated_at=%s WHERE candidate_id=%s", (now_utc(), candidate_id))
        structure = candidate["structure"] if isinstance(candidate["structure"], dict) else json.loads(candidate["structure"] or "{}")
        return {"domain": domain, "structure": structure, "version": candidate["version"], "quality": candidate.get("quality"), "promoted": True}

    def rule_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_extraction_rule_candidates WHERE candidate_id=%s", (candidate_id,))
                row = cur.fetchone()
                return self._rule_candidate_row(dict(row)) if row else None

    def list_rule_candidates(self, domain: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                clauses, params = [], []
                if domain:
                    clauses.append("domain=%s"); params.append(domain)
                if status and status != "all":
                    clauses.append("status=%s"); params.append(status)
                where = "WHERE " + " AND ".join(clauses) if clauses else ""
                params.append(limit)
                cur.execute(f"SELECT * FROM admin_extraction_rule_candidates {where} ORDER BY updated_at DESC LIMIT %s", params)
                return [self._rule_candidate_row(dict(r)) for r in cur.fetchall()]

    def rollback_rule(self, domain: str, version: str | None = None) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                params: list[Any] = [domain]
                version_clause = "AND version=%s" if version else ""
                if version:
                    params.append(version)
                cur.execute(f"SELECT * FROM admin_extraction_rule_versions WHERE domain=%s {version_clause} ORDER BY created_at DESC LIMIT 1", params)
                previous = cur.fetchone()
                if not previous:
                    return None
                previous = dict(previous)
                cur.execute("SELECT * FROM admin_extraction_rules WHERE domain=%s", (domain,))
                current = cur.fetchone()
                if current:
                    current = dict(current)
                    cur.execute("""
                        INSERT INTO admin_extraction_rule_versions (domain,structure,version,quality,status,created_at)
                        VALUES (%s,%s,%s,%s,'retired',%s)
                    """, (domain, _j(current.get("structure") or {}), current.get("version"), _j(current.get("quality")), now_utc()))
                cur.execute("""
                    INSERT INTO admin_extraction_rules (domain,structure,version,quality,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (domain) DO UPDATE
                    SET structure=EXCLUDED.structure,version=EXCLUDED.version,quality=EXCLUDED.quality,updated_at=EXCLUDED.updated_at
                """, (domain, _j(previous.get("structure") or {}), previous.get("version"), _j(previous.get("quality")), now_utc(), now_utc()))
        return {"domain": domain, "version": previous.get("version"), "structure": previous.get("structure")}

    def record_rule_event(self, event: dict[str, Any]) -> None:
        domain = event.get("domain", "")
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("INSERT INTO admin_rule_events (domain,data,created_at) VALUES (%s,%s,%s)",
                            (domain, _j(event), now_utc()))

    def _rule_row(self, row: dict[str, Any]) -> dict[str, Any]:
        for k in ("structure", "quality"):
            if isinstance(row.get(k), str):
                try:
                    row[k] = json.loads(row[k])
                except Exception:
                    pass
        return row

    def _rule_candidate_row(self, row: dict[str, Any]) -> dict[str, Any]:
        for k in ("structure", "quality", "artifact_ids"):
            if isinstance(row.get(k), str):
                try:
                    row[k] = json.loads(row[k])
                except Exception:
                    pass
        return row

    # ── Pipelines (high-level) ───────────────────────────────────────────────

    def list_pipelines_data(self) -> list[dict[str, Any]]:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipelines"):
            docs = list(db.admin_pipelines.find({}, {"_id": False})) if hasattr(db.admin_pipelines, "find") else []
            return [(doc, None, 0) for doc in docs]
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_pipelines ORDER BY updated_at DESC")
                pipelines = [dict(r) for r in cur.fetchall()]
                cur.execute("SELECT * FROM admin_pipeline_runs ORDER BY created_at DESC LIMIT 500")
                runs = [dict(r) for r in cur.fetchall()]
        latest_runs: dict[str, dict] = {}
        run_counts: dict[str, int] = {}
        for run in runs:
            pid = run.get("pipeline_id")
            if pid:
                run_counts[pid] = run_counts.get(pid, 0) + 1
                latest_runs.setdefault(pid, run)
        return [(p, latest_runs.get(p.get("pipeline_id")), run_counts.get(p.get("pipeline_id"), 0)) for p in pipelines]

    def get_pipeline_data(self, pipeline_id: str) -> tuple[dict, dict | None, int] | None:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipelines"):
            doc = db.admin_pipelines.find_one({"pipeline_id": pipeline_id}, {"_id": False})
            if not doc:
                return None
            latest_run = None
            if hasattr(db, "admin_pipeline_runs"):
                latest_run = db.admin_pipeline_runs.find_one({"pipeline_id": pipeline_id}, {"_id": False})
            latest_run = latest_run if isinstance(latest_run, dict) else None
            return dict(doc), dict(latest_run) if latest_run else None, 1 if latest_run else 0
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_pipelines WHERE pipeline_id=%s", (pipeline_id,))
                doc = cur.fetchone()
                if not doc:
                    return None
                cur.execute("SELECT * FROM admin_pipeline_runs WHERE pipeline_id=%s ORDER BY created_at DESC LIMIT 1", (pipeline_id,))
                latest_run = cur.fetchone()
                cur.execute("SELECT COUNT(*) AS n FROM admin_pipeline_runs WHERE pipeline_id=%s", (pipeline_id,))
                count = (cur.fetchone() or {}).get("n", 0)
        return dict(doc), dict(latest_run) if latest_run else None, count

    def upsert_pipeline(self, doc: dict[str, Any]) -> bool:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipelines"):
            db.admin_pipelines.update_one(
                {"pipeline_id": doc.get("pipeline_id")},
                {"$set": doc, "$setOnInsert": {"created_at": doc.get("created_at") or now_utc()}},
                upsert=True,
            )
            return True
        with self._conn() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_pipelines (pipeline_id,name,enabled,data,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (pipeline_id) DO UPDATE
                    SET name=EXCLUDED.name,enabled=EXCLUDED.enabled,data=EXCLUDED.data,updated_at=EXCLUDED.updated_at
                """, (doc.get("pipeline_id"), doc.get("name"), doc.get("enabled", True),
                      _j(doc), doc.get("created_at") or now_utc(), now_utc()))
                return True

    def delete_pipeline_data(self, pipeline_id: str) -> bool:
        with self._conn() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("DELETE FROM admin_pipelines WHERE pipeline_id=%s", (pipeline_id,))
                return cur.rowcount > 0

    def list_pipeline_run_data(self, pipeline_id: str | None, limit: int) -> list[tuple[dict, str | None]]:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipeline_runs"):
            query = {"pipeline_id": pipeline_id} if pipeline_id else {}
            rows = list(db.admin_pipeline_runs.find(query, {"_id": False}).limit(limit))
            return [(dict(row), None) for row in rows]
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                if pipeline_id:
                    cur.execute("SELECT * FROM admin_pipeline_runs WHERE pipeline_id=%s ORDER BY created_at DESC LIMIT %s", (pipeline_id, limit))
                else:
                    cur.execute("SELECT * FROM admin_pipeline_runs ORDER BY created_at DESC LIMIT %s", (limit,))
                runs = [dict(r) for r in cur.fetchall()]
                cur.execute("SELECT pipeline_id,name FROM admin_pipelines")
                names = {r["pipeline_id"]: r["name"] for r in cur.fetchall()}
        return [(run, names.get(run.get("pipeline_id"))) for run in runs]

    def insert_pipeline_run(self, run_doc: dict[str, Any]) -> None:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipeline_runs"):
            if hasattr(db.admin_pipeline_runs, "insert_one"):
                db.admin_pipeline_runs.insert_one(run_doc)
            else:
                db.admin_pipeline_runs.update_one(
                    {"run_id": run_doc.get("run_id")},
                    {"$set": run_doc, "$setOnInsert": {"created_at": run_doc.get("created_at") or now_utc()}},
                    upsert=True,
                )
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_pipeline_runs (run_id,pipeline_id,status,data,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (run_id) DO NOTHING
                """, (run_doc.get("run_id"), run_doc.get("pipeline_id"), run_doc.get("status", "pending"),
                      _j(run_doc), now_utc(), now_utc()))

    def update_pipeline_run_data(self, run_id: str, updates: dict[str, Any]) -> None:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipeline_runs"):
            db.admin_pipeline_runs.update_one({"run_id": run_id}, {"$set": updates}, upsert=False)
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM admin_pipeline_runs WHERE run_id=%s", (run_id,))
                row = cur.fetchone()
                if row:
                    merged = {**(row.get("data") or {}), **updates}
                    cur.execute("UPDATE admin_pipeline_runs SET data=%s,status=%s,updated_at=%s WHERE run_id=%s",
                                (_j(merged), updates.get("status", merged.get("status")), now_utc(), run_id))

    def get_pipeline_run_count(self, pipeline_id: str) -> int:
        with self._conn() as conn:
            if conn is None:
                return 0
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM admin_pipeline_runs WHERE pipeline_id=%s", (pipeline_id,))
                return (cur.fetchone() or {}).get("n", 0)

    def log_worker_event(self, pipeline_id: str, event: dict[str, Any]) -> None:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipeline_worker_events"):
            db.admin_pipeline_worker_events.insert_one({"pipeline_id": pipeline_id, **event, "created_at": now_utc()})
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("INSERT INTO admin_pipeline_worker_events (pipeline_id,data,created_at) VALUES (%s,%s,%s)",
                            (pipeline_id, _j(event), now_utc()))

    def acquire_pipeline_lease(self, pipeline_id: str, run_id: str, lease_seconds: int = 900) -> bool:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipelines"):
            return True
        with self._conn() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE admin_pipelines
                    SET locked_until=%s, locked_by_run_id=%s, updated_at=%s
                    WHERE pipeline_id=%s
                      AND (locked_until IS NULL OR locked_until <= %s OR locked_by_run_id=%s)
                    RETURNING pipeline_id
                """, (now_utc() + timedelta(seconds=lease_seconds), run_id, now_utc(),
                      pipeline_id, now_utc(), run_id))
                return cur.fetchone() is not None

    def release_pipeline_lease(self, pipeline_id: str, run_id: str) -> None:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipelines"):
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE admin_pipelines SET locked_until=NULL, locked_by_run_id=NULL, updated_at=%s
                    WHERE pipeline_id=%s AND locked_by_run_id=%s
                """, (now_utc(), pipeline_id, run_id))

    def renew_pipeline_lease(self, pipeline_id: str, run_id: str, lease_seconds: int) -> bool:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipelines"):
            return True
        with self._conn() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE admin_pipelines SET locked_until=%s, updated_at=%s
                    WHERE pipeline_id=%s AND locked_by_run_id=%s RETURNING pipeline_id
                """, (now_utc() + timedelta(seconds=lease_seconds), now_utc(), pipeline_id, run_id))
                return cur.fetchone() is not None

    # ── Products ─────────────────────────────────────────────────────────────

    def product_stats(self) -> dict[str, int]:
        with self._conn() as conn:
            if conn is None:
                return {"total": 0, "sources": 0}
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total FROM sc_products")
                total = (cur.fetchone() or {}).get("total", 0)
                cur.execute("SELECT COUNT(DISTINCT domain) AS sources FROM sc_products")
                sources = (cur.fetchone() or {}).get("sources", 0)
                return {"total": total, "sources": sources}

    def list_products(self, *, query_text: str | None = None, category: str | None = None, source: str | None = None, store: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                clauses, params = [], []
                if source and source != "all":
                    clauses.append("domain=%s"); params.append(source)
                if category and category != "all":
                    clauses.append("(category=%s OR normalized_category=%s)"); params += [category, category]
                if store:
                    clauses.append("(store_name ILIKE %s OR store_url ILIKE %s OR store_address ILIKE %s)"); params += [f"%{store}%", f"%{store}%", f"%{store}%"]
                if query_text:
                    clauses.append("(product_name ILIKE %s OR canonical_name ILIKE %s OR product_url ILIKE %s)"); params += [f"%{query_text}%", f"%{query_text}%", f"%{query_text}%"]
                where = "WHERE " + " AND ".join(clauses) if clauses else ""
                params.append(limit)
                cur.execute(f"SELECT * FROM sc_products {where} ORDER BY updated_at DESC LIMIT %s", params)
                rows = cur.fetchall()
        result = []
        for r in rows:
            doc = dict(r)
            embedded = doc.get("data") or {}
            if isinstance(embedded, str):
                try:
                    embedded = json.loads(embedded)
                except Exception:
                    embedded = {}
            if isinstance(embedded, dict):
                doc = {**embedded, **doc}
            result.append(self._product_view(doc))
        return result

    def ensure_canonical_columns(self) -> None:
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE sc_products ADD COLUMN IF NOT EXISTS canonical_product_id TEXT")
                cur.execute("ALTER TABLE sc_products ADD COLUMN IF NOT EXISTS canonical_key TEXT")
                cur.execute("ALTER TABLE sc_products ADD COLUMN IF NOT EXISTS canonical_match_score NUMERIC")
                cur.execute("ALTER TABLE sc_products ADD COLUMN IF NOT EXISTS canonicalized_at TIMESTAMPTZ")
                cur.execute("ALTER TABLE sc_offers ADD COLUMN IF NOT EXISTS canonical_product_id TEXT")
                cur.execute("ALTER TABLE sc_offers ADD COLUMN IF NOT EXISTS canonical_key TEXT")
                cur.execute("ALTER TABLE sc_offers ADD COLUMN IF NOT EXISTS canonicalized_at TIMESTAMPTZ")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sc_products_canonical ON sc_products(canonical_product_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sc_offers_canonical ON sc_offers(canonical_product_id)")

    def list_products_for_canonicalization(self, limit: int = 5000) -> list[dict[str, Any]]:
        self.ensure_canonical_columns()
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT product_id, product_name, canonical_name, brand, category, normalized_category,
                           product_url, domain, source_id, raw_data, updated_at
                    FROM sc_products
                    WHERE product_id IS NOT NULL
                    ORDER BY updated_at DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cur.fetchall()]

    def update_product_canonicalization(self, updates: list[dict[str, Any]]) -> dict[str, int]:
        self.ensure_canonical_columns()
        if not updates:
            return {"products_updated": 0, "offers_updated": 0}
        products_updated = 0
        offers_updated = 0
        with self._conn() as conn:
            if conn is None:
                return {"products_updated": 0, "offers_updated": 0}
            with conn.cursor() as cur:
                for item in updates:
                    cur.execute("""
                        UPDATE sc_products
                        SET canonical_product_id=%s,
                            canonical_key=%s,
                            canonical_match_score=%s,
                            canonicalized_at=%s
                        WHERE product_id=%s
                    """, (
                        item.get("canonical_product_id"),
                        item.get("canonical_key"),
                        item.get("canonical_match_score"),
                        now_utc(),
                        item.get("product_id"),
                    ))
                    products_updated += cur.rowcount or 0
                    cur.execute("""
                        UPDATE sc_offers
                        SET canonical_product_id=%s,
                            canonical_key=%s,
                            canonicalized_at=%s
                        WHERE product_id=%s
                    """, (
                        item.get("canonical_product_id"),
                        item.get("canonical_key"),
                        now_utc(),
                        item.get("product_id"),
                    ))
                    offers_updated += cur.rowcount or 0
        return {"products_updated": products_updated, "offers_updated": offers_updated}

    def search_products(self, q: str = "", source: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
        return self.list_products(query_text=q, source=source, limit=limit)

    def recent_products(self, limit: int = 10, source: str | None = None) -> list[dict[str, Any]]:
        return self.list_products(source=source, limit=limit)

    def product_sources(self) -> list[str]:
        with self._conn() as conn:
            if conn is None:
                return ["all"]
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT domain FROM sc_products WHERE domain IS NOT NULL ORDER BY domain")
                return ["all"] + [r["domain"] for r in cur.fetchall() if r["domain"]]

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
        trend = "N/A"
        if len(history) >= 2 and history[-2]["avg_price"]:
            prev = history[-2]["avg_price"]
            change = ((history[-1]["avg_price"] - prev) / prev) * 100
            trend = f"{change:+.1f}% ({history[-2]['month']} -> {history[-1]['month']})"
        return {"avg_price": round(sum(prices) / len(prices), 0) if prices else 0, "currency": "VND", "trend": trend}

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
            if price > 0:
                by_source.setdefault(source, []).append(price)
        return [{"source": s, "avg_price": round(sum(p) / len(p), 0), "count": len(p)} for s, p in sorted(by_source.items())]

    def price_history_months(self, lookback_days: int = 400) -> list[dict[str, Any]]:
        cutoff = now_utc() - timedelta(days=lookback_days)
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT TO_CHAR(updated_at,'YYYY-MM') AS month, AVG(price_numeric) AS avg_price, COUNT(*) AS count
                    FROM sc_offers WHERE price_numeric > 0 AND updated_at >= %s
                    GROUP BY month ORDER BY month
                """, (cutoff,))
                return [{"month": r["month"], "avg_price": round(float(r["avg_price"] or 0), 0), "count": r["count"]} for r in cur.fetchall()]

    # ── Raw pages / Jobs ─────────────────────────────────────────────────────

    @staticmethod
    def _domain_aliases(domain: str | None) -> list[str]:
        if not domain:
            return []
        aliases = {domain}
        aliases.add(domain.removeprefix("www."))
        if not domain.startswith("www."):
            aliases.add(f"www.{domain}")
        return list(aliases)

    def raw_pages(self, domain: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                if domain:
                    cur.execute("SELECT * FROM sc_raw_pages WHERE domain = ANY(%s) ORDER BY captured_at DESC LIMIT %s", (self._domain_aliases(domain), limit))
                else:
                    cur.execute("SELECT * FROM sc_raw_pages ORDER BY captured_at DESC LIMIT %s", (limit,))
                return [self._raw_page_view(dict(r)) for r in cur.fetchall()]

    def raw_page_domains(self, domains: list[str]) -> set[str]:
        if not domains:
            return set()
        aliases = set(domains)
        for d in domains:
            aliases.add(d.removeprefix("www."))
            if not d.startswith("www."):
                aliases.add(f"www.{d}")
        with self._conn() as conn:
            if conn is None:
                return set()
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT domain FROM sc_raw_pages WHERE domain = ANY(%s)", (list(aliases),))
                return {r["domain"] for r in cur.fetchall() if r["domain"]}

    def source_product_counts(self, domains: list[str]) -> dict[str, dict[str, int]]:
        if not domains:
            return {}
        aliases = set(domains)
        for d in domains:
            aliases.add(d.removeprefix("www."))
            if not d.startswith("www."):
                aliases.add(f"www.{d}")
        aliases_list = list(aliases)
        counts: dict[str, dict[str, int]] = {}
        with self._conn() as conn:
            if conn is None:
                return {}
            with conn.cursor() as cur:
                for field, table in (("products", "sc_products"), ("quarantined", "sc_product_quarantine")):
                    cur.execute(f"SELECT domain, COUNT(*) AS n FROM {table} WHERE domain = ANY(%s) GROUP BY domain", (aliases_list,))
                    for r in cur.fetchall():
                        counts.setdefault(r["domain"], {"products": 0, "quarantined": 0})[field] = r["n"]
        return counts

    def raw_page(self, raw_page_id: str | None, domain: str | None = None) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                if raw_page_id:
                    cur.execute("SELECT * FROM sc_raw_pages WHERE raw_page_id=%s ORDER BY captured_at DESC LIMIT 1", (raw_page_id,))
                elif domain:
                    cur.execute("SELECT * FROM sc_raw_pages WHERE domain = ANY(%s) ORDER BY captured_at DESC LIMIT 1", (self._domain_aliases(domain),))
                else:
                    return None
                row = cur.fetchone()
                return dict(row) if row else None

    def raw_page_html(self, doc: dict[str, Any] | None) -> str | None:
        if not doc:
            return None
        raw_page_id = doc.get("raw_page_id")
        if not raw_page_id:
            return None
        if doc.get("content"):
            return str(doc.get("content"))
        # Try MinIO first if configured
        from apps.admin_center.backend.minio_store import minio_store
        minio_key = doc.get("minio_key")
        if minio_key:
            content = minio_store.download(minio_key)
            if content:
                return content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        # Fall back to local filesystem
        local_raw_dir = Path(__file__).resolve().parents[4] / "store" / "raw"
        meta = doc.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        content_type = doc.get("content_type", "mhtml")
        filename = meta.get("filename") or f"{raw_page_id}.{content_type}"
        file_path = local_raw_dir / filename
        if file_path.exists():
            try:
                return file_path.read_text(encoding="utf-8")
            except Exception as exc:
                log.warning("Could not read local raw page %s: %s", raw_page_id, exc)
        return None

    def save_raw_page_content(self, raw_page: dict[str, Any], content: bytes) -> dict[str, Any]:
        payload = {
            **raw_page,
            "raw_page_id": raw_page.get("raw_page_id") or str(uuid.uuid4()),
            "domain": raw_page.get("domain") or "unknown",
            "content_type": raw_page.get("content_type", "mhtml"),
            "content_length": len(content),
            "captured_at": raw_page.get("captured_at") or now_utc(),
        }
        # Write to local filesystem
        local_raw_dir = Path(__file__).resolve().parents[4] / "store" / "raw"
        local_raw_dir.mkdir(parents=True, exist_ok=True)
        meta = payload.get("metadata") or {}
        filename = meta.get("filename") if isinstance(meta, dict) else None
        filename = filename or f"{payload['raw_page_id']}.{payload['content_type']}"
        file_path = local_raw_dir / filename
        try:
            file_path.write_bytes(content)
            (local_raw_dir / f"{payload['raw_page_id']}.meta.json").write_text(json.dumps(payload, default=str), encoding="utf-8")
        except Exception as exc:
            log.warning("Could not write local raw page %s: %s", payload["raw_page_id"], exc)
        # Optionally upload to MinIO
        from apps.admin_center.backend.minio_store import minio_store
        minio_key = minio_store.upload(filename, content)
        if minio_key:
            payload["minio_key"] = minio_key
        # Persist metadata to PostgreSQL
        with self._conn() as conn:
            if conn is not None:
                with conn.cursor() as cur:
                    meta_j = meta if isinstance(meta, dict) else {}
                    cur.execute("""
                        INSERT INTO sc_raw_pages (raw_page_id,url,domain,page_type,task_id,captured_at,content_type,content_length,status,minio_key,content,metadata,created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (raw_page_id) DO UPDATE
                        SET content_length=EXCLUDED.content_length,status=EXCLUDED.status,minio_key=EXCLUDED.minio_key,content=EXCLUDED.content,metadata=EXCLUDED.metadata
                    """, (payload["raw_page_id"], payload.get("url"), payload["domain"],
                          payload.get("page_type"), payload.get("task_id"), payload["captured_at"],
                          payload["content_type"], payload["content_length"],
                          payload.get("status", "pending"), payload.get("minio_key"),
                          content.decode("utf-8", errors="replace"), _j(meta_j), now_utc()))
        return payload

    def prune_raw_pages(self, domain: str | None = None) -> int:
        retention_days = int(os.environ.get("WORKER_RAW_PAGE_RETENTION_DAYS", 14))
        max_per_domain = int(os.environ.get("WORKER_MAX_RAW_PAGES_PER_DOMAIN", 100))
        cutoff = now_utc() - timedelta(days=max(1, retention_days))
        removed = 0
        with self._conn() as conn:
            if conn is None:
                return 0
            with conn.cursor() as cur:
                if domain:
                    cur.execute("DELETE FROM sc_raw_pages WHERE domain=%s AND captured_at<%s", (domain, cutoff))
                else:
                    cur.execute("DELETE FROM sc_raw_pages WHERE captured_at<%s", (cutoff,))
                removed += cur.rowcount
                if max_per_domain > 0:
                    domains_to_prune = [domain] if domain else []
                    if not domain:
                        cur.execute("SELECT DISTINCT domain FROM sc_raw_pages WHERE domain IS NOT NULL")
                        domains_to_prune = [r["domain"] for r in cur.fetchall()]
                    for d in domains_to_prune:
                        cur.execute("""
                            DELETE FROM sc_raw_pages WHERE raw_page_id IN (
                                SELECT raw_page_id FROM sc_raw_pages WHERE domain=%s
                                ORDER BY captured_at DESC OFFSET %s
                            )
                        """, (d, max_per_domain))
                        removed += cur.rowcount
        return removed

    def job_counts(self) -> dict[str, int]:
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        with self._conn() as conn:
            if conn is None:
                return counts
            with conn.cursor() as cur:
                try:
                    cur.execute("SELECT status, COUNT(*) AS n FROM sc_crawl_tasks GROUP BY status")
                except psycopg2.errors.UndefinedTable:
                    conn.rollback()
                    return counts
                for r in cur.fetchall():
                    normalized = {"running": "processing", "done": "completed"}.get(r["status"], r["status"])
                    if normalized in counts:
                        counts[normalized] = r["n"]
        return counts

    def jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        pages = self.raw_pages(limit=limit)
        return [{"id": p["task_id"] or p["id"], "filename": p["filename"], "source": p["domain"], "status": p.get("status", "Pending"), "timestamp": p["updated_at"]} for p in pages]

    def job_log(self, job_id: str) -> dict[str, Any] | None:
        local_raw_dir = Path(__file__).resolve().parents[4] / "store" / "raw"
        local_meta_files = list(local_raw_dir.glob(f"**/{job_id}.meta.json")) if local_raw_dir.exists() else []
        local_meta: dict[str, Any] = {}
        local_error: str | None = None
        if local_meta_files:
            try:
                local_meta = json.loads(local_meta_files[0].read_text(encoding="utf-8"))
            except Exception:
                local_meta = {}
            error_file = local_meta_files[0].parent / f"{job_id}.error"
            if error_file.exists():
                local_error = error_file.read_text(encoding="utf-8")
        with self._conn() as conn:
            page, task = None, None
            if conn is not None:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM sc_raw_pages WHERE raw_page_id=%s OR task_id=%s LIMIT 1", (job_id, job_id))
                    r = cur.fetchone()
                    page = dict(r) if r else None
                    try:
                        cur.execute("SELECT * FROM sc_crawl_tasks WHERE task_id=%s", (job_id,))
                        r = cur.fetchone()
                        task = dict(r) if r else None
                    except psycopg2.errors.UndefinedTable:
                        conn.rollback()
                        task = None
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
            events.append(f"Error in processing.")
        return {"job_id": job_id, "events": events, "metadata": (page.get("metadata") if page else local_meta) or {}, "error": (task.get("last_error") if task else local_error), "output_summary": task.get("output_summary") if task else None}

    # ── Dedup candidates ─────────────────────────────────────────────────────

    def sync_dedup_candidates(self, candidates: list[dict[str, Any]]) -> None:
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                for c in candidates:
                    cur.execute("""
                        INSERT INTO admin_dedup_candidates (candidate_id,confidence,reasons,left_product,right_product,status,created_at,updated_at)
                        VALUES (%s,%s,%s,%s,%s,'pending',%s,%s)
                        ON CONFLICT (candidate_id) DO UPDATE
                        SET confidence=EXCLUDED.confidence,reasons=EXCLUDED.reasons,
                            left_product=EXCLUDED.left_product,right_product=EXCLUDED.right_product,updated_at=EXCLUDED.updated_at
                    """, (c["id"], c.get("confidence"), _j(c.get("reasons", [])), _j(c.get("left", {})), _j(c.get("right", {})), now_utc(), now_utc()))

    def list_dedup_candidates(self, status: str | None, limit: int) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                if status and status != "all":
                    cur.execute("SELECT * FROM admin_dedup_candidates WHERE status=%s ORDER BY confidence DESC LIMIT %s", (status, limit))
                else:
                    cur.execute("SELECT * FROM admin_dedup_candidates ORDER BY status, confidence DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
        result = []
        for r in [dict(r) for r in rows]:
            row = r.copy()
            for k in ("reasons", "left_product", "right_product"):
                if isinstance(row.get(k), str):
                    try:
                        row[k] = json.loads(row[k])
                    except Exception:
                        row[k] = {} if k != "reasons" else []
            row["id"] = row.pop("candidate_id", row.get("id"))
            row["left"] = row.pop("left_product", {})
            row["right"] = row.pop("right_product", {})
            result.append(row)
        return result

    def update_dedup_candidate(self, candidate_id: str, status: str, note: str | None, role: str) -> bool:
        with self._conn() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("UPDATE admin_dedup_candidates SET status=%s,note=%s,updated_by_role=%s,updated_at=%s WHERE candidate_id=%s",
                            (status, note, role, now_utc(), candidate_id))
                return cur.rowcount > 0

    # ── AI review candidates ─────────────────────────────────────────────────

    def sync_ai_review_candidates(self, candidates: list[dict[str, Any]]) -> None:
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_ai_review_candidates"):
            for c in candidates:
                review_id = c.get("review_id") or c.get("id")
                if review_id:
                    db.admin_ai_review_candidates.update_one(
                        {"review_id": review_id},
                        {"$set": c, "$setOnInsert": {"created_at": now_utc()}},
                        upsert=True,
                    )
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                for c in candidates:
                    review_id = c.get("review_id") or c.get("id")
                    if not review_id:
                        continue
                    domain = c.get("domain", "")
                    entity_type = c.get("entity_type", "")
                    status = c.get("review_status") or c.get("status") or "needs_review"
                    confidence = c.get("confidence")
                    reason = c.get("reason", "")
                    cur.execute("""
                        INSERT INTO admin_ai_review_candidates (review_id,domain,entity_type,status,confidence,reason,payload,created_at,updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (review_id) DO UPDATE
                        SET domain=EXCLUDED.domain,entity_type=EXCLUDED.entity_type,
                            confidence=EXCLUDED.confidence,reason=EXCLUDED.reason,payload=EXCLUDED.payload,updated_at=EXCLUDED.updated_at
                    """, (review_id, domain, entity_type, status, confidence, reason, _j(c), now_utc(), now_utc()))

    def list_ai_review_candidates(self, status: str | None, domain: str | None, limit: int) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                clauses, params = [], []
                if status and status != "all":
                    clauses.append("status=%s"); params.append(status)
                if domain and domain != "all":
                    clauses.append("domain=%s"); params.append(domain)
                where = "WHERE " + " AND ".join(clauses) if clauses else ""
                params.append(limit)
                cur.execute(f"SELECT * FROM admin_ai_review_candidates {where} ORDER BY status, confidence DESC, updated_at DESC LIMIT %s", params)
                rows = cur.fetchall()
        result = []
        for r in rows:
            row = dict(r)
            payload = row.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            merged = {**payload, "review_id": row["review_id"], "domain": row["domain"],
                      "entity_type": row["entity_type"], "status": row["status"],
                      "confidence": float(row["confidence"] or 0) if row.get("confidence") is not None else None,
                      "reason": row["reason"], "note": row.get("note"), "updated_at": row.get("updated_at")}
            result.append(merged)
        return result

    def update_ai_review_candidate(self, review_id: str, status: str, note: str | None, role: str) -> bool:
        with self._conn() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("UPDATE admin_ai_review_candidates SET status=%s,note=%s,updated_by_role=%s,updated_at=%s WHERE review_id=%s",
                            (status, note, role, now_utc(), review_id))
                return cur.rowcount > 0

    def ai_review_candidate(self, review_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_ai_review_candidates WHERE review_id=%s", (review_id,))
                row = cur.fetchone()
                if not row:
                    return None
                row = dict(row)
                payload = row.get("payload") or {}
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                return {**payload, "review_id": row["review_id"], "status": row["status"], "domain": row["domain"]}

    # ── Generation prompts ───────────────────────────────────────────────────

    def get_latest_prompt(self, key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sc_generation_prompts WHERE key=%s ORDER BY version DESC LIMIT 1", (key,))
                row = cur.fetchone()
                return dict(row) if row else None

    def save_new_prompt_version(self, key: str, content: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(version) AS v FROM sc_generation_prompts WHERE key=%s", (key,))
                r = cur.fetchone()
                new_version = ((r.get("v") or 0) + 1) if r else 1
                doc = {"key": key, "version": new_version, "content": content, "created_at": now_utc()}
                cur.execute("INSERT INTO sc_generation_prompts (key,version,content,created_at) VALUES (%s,%s,%s,%s)",
                            (key, new_version, content, now_utc()))
        return doc

    def list_prompt_versions(self, key: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sc_generation_prompts WHERE key=%s ORDER BY version DESC", (key,))
                return [dict(r) for r in cur.fetchall()]

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def rule_version(structure: dict[str, Any]) -> str:
        raw = json.dumps(structure, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _raw_page_view(self, doc: dict[str, Any]) -> dict[str, Any]:
        meta = doc.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        content_type = doc.get("content_type", "mhtml")
        captured_at = doc.get("captured_at") or doc.get("created_at") or now_utc()
        status = doc.get("status") or meta.get("status") or "pending"
        return {
            "id": doc.get("raw_page_id"),
            "filename": meta.get("filename") or f"{doc.get('raw_page_id')}.{content_type}",
            "path": f"pg://sc_raw_pages/{doc.get('raw_page_id')}",
            "domain": doc.get("domain") or meta.get("domain") or "unknown",
            "task_id": doc.get("task_id") or doc.get("raw_page_id"),
            "url": doc.get("url"),
            "page_type": meta.get("page_type", doc.get("page_type", "unknown")),
            "size": doc.get("content_length") or meta.get("size"),
            "updated_at": captured_at,
            "status": {"pending": "Pending", "running": "Processing", "processing": "Processing",
                       "done": "Completed", "completed": "Completed", "failed": "Failed"}.get(str(status).lower(), str(status).title()),
        }

    def _product_view(self, doc: dict[str, Any]) -> dict[str, Any]:
        price = doc.get("price_numeric") or doc.get("price")
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
            "name": name, "price": price_numeric, "price_numeric": price_numeric,
            "price_status": doc.get("price_status") or ("FOUND" if price_numeric and price_numeric > 0 else "MISSING"),
            "original_price": doc.get("old_price") or doc.get("original_price"),
            "currency": doc.get("currency", "VND"), "url": product_url,
            "source": doc.get("domain") or doc.get("source_site"),
            "source_site": doc.get("domain") or doc.get("source_site"),
            "category": category, "image": doc.get("image_url"), "image_url": doc.get("image_url"),
            "brand": doc.get("brand"),
            "store_name": doc.get("store_name") or raw_data.get("store_name") or "",
            "store_url": doc.get("store_url") or raw_data.get("store_url") or "",
            "store_address": doc.get("store_address") or raw_data.get("store_address"),
            "store_channel": doc.get("store_channel") or raw_data.get("store_channel"),
            "address_status": doc.get("address_status") or raw_data.get("address_status") or "MISSING",
            "store_phone": doc.get("store_phone") or raw_data.get("store_phone") or "",
            "data_origin": doc.get("data_origin"), "rule_version": doc.get("rule_version"),
            "extraction_method": doc.get("extraction_method"), "validation_score": doc.get("validation_score"),
            "canonical_product_id": doc.get("canonical_product_id"),
            "canonical_key": doc.get("canonical_key"),
            "canonical_match_score": doc.get("canonical_match_score"),
            "canonicalized_at": doc.get("canonicalized_at"),
            "updated_at": doc.get("updated_at") or doc.get("created_at"),
        }

    @staticmethod
    def _normalize_price(value: Any) -> float | None:
        if isinstance(value, (Decimal, int, float)):
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

    def _load_category_rules(self) -> list[tuple[str, list[str]]]:
        """Load category rules from the DB, refresh every 5 minutes. Falls back to static rules."""
        _REFRESH_SECS = 300
        with self._lock:
            if self._category_rules_cache is not None and (time.monotonic() - self._category_rules_loaded_at) < _REFRESH_SECS:
                return self._category_rules_cache
        try:
            with self._conn() as conn:
                if conn is None:
                    raise RuntimeError("no db")
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT category, keywords FROM category_rules WHERE is_active = TRUE ORDER BY priority DESC"
                    )
                    rows = cur.fetchall() or []
            rules = [(row["category"], list(row["keywords"])) for row in rows if row.get("keywords")]
            if not rules:
                raise ValueError("empty rules table")
            with self._lock:
                self._category_rules_cache = rules
                self._category_rules_loaded_at = time.monotonic()
            return rules
        except Exception as exc:
            log.debug("category_rules DB load failed (%s); using static fallback", exc)
            return self._STATIC_CATEGORY_RULES

    def _normalize_category(self, *values: Any) -> str:
        """Match product text against category rules loaded from DB (with static fallback)."""
        if not isinstance(self, AdminPgStore):
            values = (self, *values)
            rules = AdminPgStore._STATIC_CATEGORY_RULES
        else:
            rules = self._load_category_rules()
        haystack = " ".join(" ".join(str(v or "").lower().split()) for v in values if v)
        if not haystack:
            return "Khác"
        for category, keywords in rules:
            if any(k in haystack for k in keywords):
                return category
        return "Khác"

    # ── Extra pipeline helpers ────────────────────────────────────────────────

    def recently_captured_raw_page(self, url: str, min_hours: int) -> dict[str, Any] | None:
        """Return a recently-captured raw page for *url* or None if not found / too old."""
        if min_hours <= 0:
            return None
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "sc_raw_pages"):
            doc = db.sc_raw_pages.find_one({"url": url}, {"_id": False})
            return dict(doc) if isinstance(doc, dict) else None
        cutoff = now_utc() - timedelta(hours=min_hours)
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM sc_raw_pages WHERE url=%s AND captured_at>=%s ORDER BY captured_at DESC LIMIT 1",
                    (url, cutoff),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_enabled_pipeline_docs(self) -> list[dict[str, Any]]:
        """Return flat pipeline dicts for all enabled pipelines (used by cron worker)."""
        with self._conn() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_pipelines WHERE enabled=TRUE ORDER BY updated_at DESC")
                rows = cur.fetchall()
        result = []
        for row in rows:
            row = dict(row)
            data = row.get("data") or {}
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    data = {}
            result.append({**row, **data, "pipeline_id": row.get("pipeline_id"), "name": row.get("name"), "enabled": row.get("enabled", data.get("enabled", True))})
        return result

    def get_pipeline_doc(self, pipeline_id: str) -> dict[str, Any] | None:
        """Return the full pipeline document dict (merges columns + JSONB data)."""
        result = self.get_pipeline_data(pipeline_id)
        if result is None:
            return None
        pg_row, _, _ = result
        data = pg_row.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        return {**pg_row, **data, "pipeline_id": pg_row.get("pipeline_id"), "name": pg_row.get("name"), "enabled": pg_row.get("enabled", data.get("enabled", True))}

    def get_latest_pipeline_run(self, pipeline_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            if conn is None:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM admin_pipeline_runs WHERE pipeline_id=%s ORDER BY created_at DESC LIMIT 1", (pipeline_id,))
                row = cur.fetchone()
                if not row:
                    return None
                row = dict(row)
                data = row.get("data") or {}
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except Exception:
                        data = {}
                return {**data, "run_id": row.get("run_id"), "pipeline_id": row.get("pipeline_id"), "status": row.get("status")}

    def update_pipeline_meta(self, pipeline_id: str, updates: dict[str, Any]) -> None:
        """Merge scalar metadata into admin_pipelines.data JSONB column."""
        db = self.get_db()
        if db is not None and not isinstance(db, _PgCompatDb) and hasattr(db, "admin_pipelines"):
            db.admin_pipelines.update_one({"pipeline_id": pipeline_id}, {"$set": updates}, upsert=False)
            return
        with self._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE admin_pipelines
                    SET data = data || %s::jsonb, updated_at = %s
                    WHERE pipeline_id = %s
                """, (_j(updates), now_utc(), pipeline_id))

    def pipeline_overview_stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            if conn is None:
                return {"total": 0, "enabled": 0, "runs": 0, "running": 0}
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM admin_pipelines")
                total = (cur.fetchone() or {}).get("n", 0)
                cur.execute("SELECT COUNT(*) AS n FROM admin_pipelines WHERE enabled = TRUE")
                enabled = (cur.fetchone() or {}).get("n", 0)
                cur.execute("SELECT COUNT(*) AS n FROM admin_pipeline_runs")
                runs = (cur.fetchone() or {}).get("n", 0)
                cur.execute("SELECT COUNT(*) AS n FROM admin_pipeline_runs WHERE status = 'running'")
                running = (cur.fetchone() or {}).get("n", 0)
            return {"total": total, "enabled": enabled, "runs": runs, "running": running}


class _PgUpdateResult:
    def __init__(self, modified_count: int = 0) -> None:
        self.modified_count = modified_count


class _PgFindResult(list):
    def sort(self, *args: Any, **kwargs: Any):
        return self

    def limit(self, count: int):
        return _PgFindResult(self[:count])


class _PgCompatCollection:
    _PRIMARY_KEYS = {
        "sc_products": "product_id",
        "sc_offers": "offer_id",
        "sc_price_observations": "observation_id",
        "sc_store_locations": "store_location_id",
        "sc_synthetic_products": "synthetic_id",
        "sc_synthetic_quarantine": "synthetic_id",
    }

    def __init__(self, store: AdminPgStore, table: str) -> None:
        self.store = store
        self.table = table

    def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> _PgUpdateResult:
        payload = dict(update.get("$set") or {})
        payload.update(update.get("$setOnInsert") or {})
        key = self._key_from_query(query)
        if not key or not payload:
            return _PgUpdateResult(0)
        self._upsert(key, payload)
        return _PgUpdateResult(1)

    def update_many(self, query: dict[str, Any], update: dict[str, Any]) -> _PgUpdateResult:
        payload = dict(update.get("$set") or {})
        rows = self.find(query)
        modified = 0
        for row in rows:
            key = row.get(self._PRIMARY_KEYS.get(self.table, "id"))
            if key:
                self._upsert(key, {**row, **payload})
                modified += 1
        return _PgUpdateResult(modified)

    def insert_many(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.insert_one(row)

    def insert_one(self, row: dict[str, Any]) -> None:
        if self.table == "sc_product_quarantine":
            self._insert_quarantine(row)
            return
        key_name = self._PRIMARY_KEYS.get(self.table)
        if key_name and row.get(key_name):
            self._upsert(str(row[key_name]), row)

    def find_one(self, query: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        rows = self.find(query, projection)
        return rows[0] if rows else None

    def find(self, query: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> _PgFindResult:
        where, params = self._where(query or {})
        sql = f"SELECT * FROM {self.table} {where}"
        with self.store._conn() as conn:
            if conn is None:
                return _PgFindResult()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return _PgFindResult([dict(row) for row in cur.fetchall()])

    def _key_from_query(self, query: dict[str, Any]) -> tuple[str, Any] | None:
        key_name = self._PRIMARY_KEYS.get(self.table)
        if key_name and query.get(key_name):
            return key_name, query[key_name]
        for key, value in query.items():
            if not isinstance(value, dict):
                return key, value
        return None

    def _columns(self) -> set[str]:
        with self.store._conn() as conn:
            if conn is None:
                return set()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                    (self.table,),
                )
                return {row["column_name"] for row in cur.fetchall()}

    def _upsert(self, key: tuple[str, Any], payload: dict[str, Any]) -> None:
        columns = self._columns()
        key_name, key_value = key
        payload = {k: v for k, v in payload.items() if k in columns}
        payload[key_name] = key_value
        if "updated_at" in columns and "updated_at" not in payload:
            payload["updated_at"] = now_utc()
        names = list(payload.keys())
        placeholders = ", ".join(["%s"] * len(names))
        assignments = ", ".join(f"{name}=EXCLUDED.{name}" for name in names if name != key_name)
        sql = (
            f"INSERT INTO {self.table} ({', '.join(names)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({key_name}) DO UPDATE SET {assignments}"
        )
        values = [_j(value) if isinstance(value, (dict, list)) else value for value in (payload[name] for name in names)]
        with self.store._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute(sql, values)

    def _insert_quarantine(self, row: dict[str, Any]) -> None:
        columns = self._columns()
        payload = {k: v for k, v in row.items() if k in columns}
        if not payload:
            return
        names = list(payload.keys())
        values = [_j(value) if isinstance(value, (dict, list)) else value for value in (payload[name] for name in names)]
        with self.store._conn() as conn:
            if conn is None:
                return
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {self.table} ({', '.join(names)}) VALUES ({', '.join(['%s'] * len(names))})",
                    values,
                )

    def _where(self, query: dict[str, Any]) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in query.items():
            if isinstance(value, dict) and "$in" in value:
                clauses.append(f"{key} = ANY(%s)")
                params.append(list(value["$in"]))
            elif isinstance(value, dict):
                continue
            else:
                clauses.append(f"{key}=%s")
                params.append(value)
        return ("WHERE " + " AND ".join(clauses), params) if clauses else ("", params)


class _PgCompatDb:
    def __init__(self, store: AdminPgStore) -> None:
        self.store = store

    def __getattr__(self, table: str) -> _PgCompatCollection:
        return _PgCompatCollection(self.store, table)
