"""
DatabaseManager — Quản lý lưu trữ và tracking cho Smart Crawler.
Dùng Psycopg2 để tương tác với PostgreSQL.
"""
from __future__ import annotations

import os
import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor, Json

from shared.config import settings

logger = logging.getLogger("smart_crawler.db_manager")

class DatabaseManager:
    """Quản lý kết nối và thực thi queries cho hệ thống tracking."""

    def __init__(self):
        self.conn_params = {
            "dbname": settings.POSTGRES_DB,
            "user": settings.POSTGRES_USER,
            "password": settings.POSTGRES_PASSWORD,
            "host": settings.POSTGRES_HOST,
            "port": str(settings.POSTGRES_PORT),
        }
        self.conn = None

    def _get_conn(self):
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(**self.conn_params)
                self.conn.autocommit = True
            except Exception as e:
                logger.error(f"❌ Database connection failed: {e}")
                return None
        return self.conn

    # ── Domain Intelligence ───────────────────────────────────────────────────

    def upsert_domain(self, info: Dict[str, Any]) -> None:
        """Lưu hoặc cập nhật thông tin phân tích domain."""
        conn = self._get_conn()
        if not conn: return

        sql = """
            INSERT INTO sc_domains (
                domain, strategy, can_crawl_direct, has_api, has_listing, 
                anti_bot, js_required, status_code, redirect_url, notes, last_analyzed
            ) VALUES (
                %(domain)s, %(strategy)s, %(can_crawl_direct)s, %(has_api)s, %(has_listing)s,
                %(anti_bot)s, %(js_required)s, %(status_code)s, %(redirect_url)s, %(notes)s, NOW()
            ) ON CONFLICT (domain) DO UPDATE SET
                strategy = EXCLUDED.strategy,
                can_crawl_direct = EXCLUDED.can_crawl_direct,
                has_api = EXCLUDED.has_api,
                has_listing = EXCLUDED.has_listing,
                anti_bot = EXCLUDED.anti_bot,
                js_required = EXCLUDED.js_required,
                status_code = EXCLUDED.status_code,
                redirect_url = EXCLUDED.redirect_url,
                notes = EXCLUDED.notes,
                last_analyzed = NOW();
        """
        with conn.cursor() as cur:
            cur.execute(sql, info)

    def get_domain_info(self, domain_name: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        if not conn: return None
        
        sql = "SELECT * FROM sc_domains WHERE domain = %s"
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (domain_name,))
            return cur.fetchone()

    # ── Structure Management ──────────────────────────────────────────────────

    def save_structure(self, domain: str, structure: Dict[str, Any], source: str = "llm") -> None:
        """Lưu structure JSON vào DB."""
        conn = self._get_conn()
        if not conn: return

        # Deactivate old versions
        deactivate_sql = "UPDATE sc_structures SET is_active = FALSE WHERE domain = %s"
        
        insert_sql = """
            INSERT INTO sc_structures (
                domain, structure_json, source, page_type, llm_model, is_active
            ) VALUES (%s, %s, %s, %s, %s, TRUE)
        """
        
        with conn.cursor() as cur:
            cur.execute(deactivate_sql, (domain,))
            cur.execute(insert_sql, (
                domain, 
                Json(structure), 
                source, 
                structure.get("page_type"),
                structure.get("_llm_model")
            ))

    def get_active_structure(self, domain: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        if not conn: return None

        sql = "SELECT structure_json FROM sc_structures WHERE domain = %s AND is_active = TRUE ORDER BY created_at DESC LIMIT 1"
        with conn.cursor() as cur:
            cur.execute(sql, (domain,))
            res = cur.fetchone()
            return res[0] if res else None

    # ── Crawl Session ─────────────────────────────────────────────────────────

    def start_session(self, domain: str, strategy: str, start_url: str) -> str:
        session_id = str(uuid.uuid4())
        conn = self._get_conn()
        if not conn: return session_id

        sql = """
            INSERT INTO sc_crawl_sessions (session_id, domain, strategy_used, start_url, status)
            VALUES (%s, %s, %s, %s, 'running')
        """
        with conn.cursor() as cur:
            cur.execute(sql, (session_id, domain, strategy, start_url))
        return session_id

    def update_session_stats(self, session_id: str, stats: Dict[str, Any]) -> None:
        conn = self._get_conn()
        if not conn: return

        sql = """
            UPDATE sc_crawl_sessions SET
                total_pages = %(total_pages)s,
                total_products = %(total_products)s,
                fallback_count = %(fallback_count)s,
                success_rate = %(success_rate)s,
                status = %(status)s,
                error_message = %(error_message)s,
                completed_at = NOW()
            WHERE session_id = %(session_id)s
        """
        params = {"session_id": session_id, **stats}
        with conn.cursor() as cur:
            cur.execute(sql, params)

    # ── Data Storage ──────────────────────────────────────────────────────────

    def save_products(self, products: List[Dict[str, Any]]) -> int:
        """Bulk upsert products vào database."""
        if not products:
            return 0
        
        conn = self._get_conn()
        if not conn: return len(products)
        
        sql = """
            INSERT INTO products (
                domain, product_name, brand, category, alcohol_percent,
                volume_ml, price, price_numeric, old_price, stock_status,
                rating, review_count, image_url, product_url, source_strategy,
                confidence_score, validation_status
            ) VALUES %s
            ON CONFLICT (product_url) DO UPDATE SET
                price = EXCLUDED.price,
                price_numeric = EXCLUDED.price_numeric,
                stock_status = EXCLUDED.stock_status,
                confidence_score = EXCLUDED.confidence_score,
                validation_status = EXCLUDED.validation_status,
                updated_at = NOW();
        """
        
        # Format values cho execute_values
        from psycopg2.extras import execute_values
        
        values = [
            (
                p.get("domain"), p.get("product_name"), p.get("brand"),
                p.get("category"), p.get("alcohol_percent"), p.get("volume_ml"), p.get("price"),
                p.get("price_numeric"), p.get("old_price"), p.get("stock_status"),
                p.get("rating"), p.get("review_count"), p.get("image_url"), p.get("product_url"),
                p.get("source_strategy"), p.get("confidence_score", 1.0), p.get("validation_status", "valid")
            )
            for p in products
        ]
        
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
        
        return len(products)

    def log_page(self, session_id: str, log_info: Dict[str, Any]) -> None:
        conn = self._get_conn()
        if not conn: return

        sql = """
            INSERT INTO sc_page_logs (
                session_id, page_url, page_type, products_found, used_fallback, http_status, error
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                session_id, log_info.get("page_url"), log_info.get("page_type"),
                log_info.get("products_found", 0), log_info.get("used_fallback", False),
                log_info.get("http_status"), log_info.get("error")
            ))

    def close(self):
        if self.conn:
            self.conn.close()
