"""Unit tests for extraction_service helper functions.

Uses unittest.mock to avoid live Gemini / DB calls.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_CENTER_SKIP_AUTO_VALIDATE", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestSyntheticValue(unittest.TestCase):
    def _call(self, row, *names):
        from apps.admin_center.backend.extraction_service import _synthetic_value
        return _synthetic_value(row, *names)

    def test_returns_first_match(self):
        row = {"name": "Sữa Vinamilk", "product_name": "Other"}
        self.assertEqual(self._call(row, "name", "product_name"), "Sữa Vinamilk")

    def test_falls_through_to_second(self):
        row = {"product_name": "Vinamilk 1L"}
        self.assertEqual(self._call(row, "name", "product_name"), "Vinamilk 1L")

    def test_returns_none_when_missing(self):
        row = {"category": "Sữa"}
        self.assertIsNone(self._call(row, "name", "product_name"))

    def test_empty_string_is_skipped(self):
        row = {"name": ""}
        self.assertIsNone(self._call(row, "name"))

    def test_case_insensitive_key_lookup(self):
        row = {"Name": "Test"}
        self.assertEqual(self._call(row, "name"), "Test")


class TestSemanticValidateSyntheticRows(unittest.TestCase):
    def _call(self, rows, product_types=None):
        from apps.admin_center.backend.extraction_service import _semantic_validate_synthetic_rows
        return _semantic_validate_synthetic_rows(rows, product_types or [])

    def _good_row(self, **overrides):
        base = {
            "name": "Sữa Vinamilk 1L",
            "category": "Sữa",
            "price": "32000",
            "store_name": "Coopmart",
            "rating": "4.5",
            "url": "https://vinamilk.com/p/1",
            "source": "https://vinamilk.com",
        }
        base.update(overrides)
        return base

    def test_valid_row_accepted(self):
        result = self._call([self._good_row()])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["valid_rows"], 1)
        self.assertEqual(result["errors"], [])

    def test_missing_name_rejected(self):
        result = self._call([self._good_row(name="")])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["invalid_rows"], 1)
        self.assertTrue(any("name" in e["reasons"][0] for e in result["errors"]))

    def test_zero_price_rejected(self):
        result = self._call([self._good_row(price="0")])
        self.assertFalse(result["accepted"])
        self.assertTrue(any("price" in e["reasons"][0] for e in result["errors"]))

    def test_rating_out_of_range_rejected(self):
        result = self._call([self._good_row(rating="2.5")])
        self.assertFalse(result["accepted"])
        self.assertTrue(any("rating" in e["reasons"][0] for e in result["errors"]))

    def test_bad_url_rejected(self):
        result = self._call([self._good_row(url="not-a-url")])
        self.assertFalse(result["accepted"])

    def test_duplicate_rows_flagged(self):
        row = self._good_row()
        result = self._call([row, row])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["invalid_rows"], 1)

    def test_category_filter_applied(self):
        result = self._call([self._good_row(category="WrongCategory")], product_types=["Sữa"])
        self.assertFalse(result["accepted"])
        self.assertTrue(any("category" in e["reasons"][0] for e in result["errors"]))

    def test_empty_product_types_skips_category_check(self):
        result = self._call([self._good_row(category="AnythingGoes")], product_types=[])
        self.assertTrue(result["accepted"])

    def test_multiple_valid_rows(self):
        rows = [
            self._good_row(name="Sữa A", url="https://x.com/a"),
            self._good_row(name="Sữa B", url="https://x.com/b"),
        ]
        result = self._call(rows)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["valid_rows"], 2)


class TestDefaultSyntheticColumns(unittest.TestCase):
    def test_default_columns_defined(self):
        from apps.admin_center.backend.extraction_service import DEFAULT_SYNTHETIC_COLUMNS
        self.assertIn("name", DEFAULT_SYNTHETIC_COLUMNS)
        self.assertIn("price", DEFAULT_SYNTHETIC_COLUMNS)
        self.assertIn("category", DEFAULT_SYNTHETIC_COLUMNS)

    def test_allowed_columns_superset_of_default(self):
        from apps.admin_center.backend.extraction_service import (
            ALLOWED_SYNTHETIC_COLUMNS,
            DEFAULT_SYNTHETIC_COLUMNS,
        )
        for col in DEFAULT_SYNTHETIC_COLUMNS:
            self.assertIn(col, ALLOWED_SYNTHETIC_COLUMNS, f"{col} missing from ALLOWED")

    def test_required_columns_subset_of_allowed(self):
        from apps.admin_center.backend.extraction_service import (
            ALLOWED_SYNTHETIC_COLUMNS,
            SYNTHETIC_REQUIRED_COLUMNS,
        )
        for col in SYNTHETIC_REQUIRED_COLUMNS:
            self.assertIn(col, ALLOWED_SYNTHETIC_COLUMNS)


if __name__ == "__main__":
    unittest.main()
