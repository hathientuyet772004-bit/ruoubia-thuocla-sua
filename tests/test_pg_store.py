"""Unit tests for AdminPgStore.

These tests mock psycopg2 at the module level so they run without a live DB.
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("ADMIN_CENTER_SKIP_AUTO_VALIDATE", "1")
os.environ.setdefault("DATABASE_URL", "postgresql://localhost/test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestNormalizeCategory(unittest.TestCase):
    """Tests for the static _normalize_category helper (no DB needed)."""

    def _call(self, *values):
        from apps.admin_center.backend.pg_store import AdminPgStore
        return AdminPgStore._normalize_category(*values)

    def test_ruou_keywords(self):
        self.assertEqual(self._call("rượu", "vinmart"), "Rượu")

    def test_beer_keywords(self):
        self.assertEqual(self._call("bia larue lager"), "Bia")

    def test_milk_keywords(self):
        self.assertEqual(self._call("sữa vinamilk"), "Sữa")

    def test_tobacco(self):
        self.assertEqual(self._call("cigarette"), "Thuốc lá")

    def test_default_khac(self):
        self.assertEqual(self._call("nước khoáng"), "Khác")

    def test_multiple_args(self):
        self.assertEqual(self._call("mì tôm", "whisky flavour"), "Rượu")

    def test_empty(self):
        self.assertEqual(self._call("", None, ""), "Khác")


class TestAdminPgStoreNoConnection(unittest.TestCase):
    """Tests that gracefully degrade when the DB pool is unavailable."""

    def _make_store(self):
        from apps.admin_center.backend.pg_store import AdminPgStore
        store = AdminPgStore.__new__(AdminPgStore)
        store._pool = None
        store._pool_error = "unit-test: no DB"
        import threading
        store._lock = threading.RLock()
        store._unavailable_until = float("inf")
        return store

    def test_list_sources_returns_empty_on_no_db(self):
        store = self._make_store()
        result = store.list_sources()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_connection_status_shows_degraded(self):
        store = self._make_store()
        status = store.connection_status()
        self.assertFalse(status["db_available"])
        self.assertEqual(status["data_status"], "degraded")

    def test_ready_returns_false_without_pool(self):
        store = self._make_store()
        self.assertFalse(store.ready())


class TestAdminPgStoreMocked(unittest.TestCase):
    """Tests with a fully mocked psycopg2 connection."""

    def _make_store_with_mock_conn(self, mock_rows=None):
        from apps.admin_center.backend.pg_store import AdminPgStore
        import threading

        store = AdminPgStore.__new__(AdminPgStore)
        store._lock = threading.RLock()
        store._unavailable_until = 0.0
        store._pool_error = None

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows or []
        mock_cursor.fetchone.return_value = {"n": 0}
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        store._pool = mock_pool
        store._mock_cursor = mock_cursor
        store._mock_conn = mock_conn
        return store

    def test_list_sources_maps_rows(self):
        from apps.admin_center.backend.pg_store import AdminPgStore
        store = self._make_store_with_mock_conn(mock_rows=[
            {"id": 1, "name": "Vinmart", "url": "https://vinmart.com", "type": "E-commerce", "category": "Sữa", "note": None, "status": "active"},
        ])
        sources = store.list_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["name"], "Vinmart")

    def test_search_products_empty(self):
        store = self._make_store_with_mock_conn(mock_rows=[])
        result = store.search_products(q="", source="all", limit=10)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_connection_status_ok_with_pool(self):
        store = self._make_store_with_mock_conn()
        status = store.connection_status()
        self.assertTrue(status["db_available"])
        self.assertEqual(status["data_status"], "ok")


class TestCategoryRulesFromDB(unittest.TestCase):
    """Tests for DB-driven category normalization (if implemented)."""

    def test_normalize_with_db_rules_falls_back_to_static(self):
        from apps.admin_center.backend.pg_store import AdminPgStore
        import threading

        store = AdminPgStore.__new__(AdminPgStore)
        store._lock = threading.RLock()
        store._unavailable_until = float("inf")
        store._pool = None
        store._pool_error = "no db"
        store._category_rules_cache = None

        result = store._normalize_category("bia", "larue")
        self.assertEqual(result, "Bia")


if __name__ == "__main__":
    unittest.main()
