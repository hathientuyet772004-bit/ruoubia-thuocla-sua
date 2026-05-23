from __future__ import annotations

import json
import tempfile
import unittest
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import main as admin
from apps.admin_center.backend.mongo_store import AdminMongoStore
from apps.admin_center.backend.settings import Settings


class AdminCenterApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.structures = self.root / "structures"
        self.rule_path = self.structures / "example.test.json"
        self.rule_path.parent.mkdir(parents=True)
        self.rule_path.write_text(json.dumps({
            "domain": "example.test",
            "listing": {"fields": [{"name": "product_name", "selector": "h3", "required": True}]},
            "product_detail": {"fields": [{"name": "price", "selector": ".price"}]},
        }), encoding="utf-8")
        raw_dir = self.root / "store" / "raw" / "example.test"
        raw_dir.mkdir(parents=True)
        raw = raw_dir / "task-1.mhtml"
        raw.write_text("<html><body><h3>Milk</h3><span class='price'>29000</span></body></html>", encoding="utf-8")
        Path(f"{raw}.meta.json").write_text(json.dumps({"url": "https://example.test/p/1", "page_type": "product"}), encoding="utf-8")
        output_dir = self.root / "store" / "outputs"
        output_dir.mkdir(parents=True)
        (output_dir / "products.json").write_text(json.dumps({
            "source_site": "example.test",
            "products": [
                {"name": "Sua tuoi 1L", "url": "https://example.test/p/1"},
                {"name": "Sua tuoi 1L", "url": "https://mirror.test/p/1"},
            ],
        }), encoding="utf-8")
        self.rule = json.loads(self.rule_path.read_text(encoding="utf-8"))
        self.rule_row = {
            "domain": "example.test",
            "structure": self.rule,
            "version": admin.mongo_store.rule_version(self.rule),
            "updated_at": datetime(2026, 5, 22, 1, 2, 3),
        }

        def save_rule(domain, structure, expected_version):
            if expected_version and expected_version != self.rule_row["version"]:
                return {"conflict": True, "version": self.rule_row["version"]}
            self.rule_row["structure"] = structure
            self.rule_row["version"] = admin.mongo_store.rule_version(structure)
            return self.rule_row

        self.patches = [
            patch.object(deps, "project_root", self.root),
            patch.object(deps, "structures_dir", self.structures),
            patch.object(deps, "admin_store_dir", self.root / "store" / "admin"),
            patch.object(deps, "dedup_queue_path", self.root / "store" / "admin" / "dedup_queue.json"),
            patch.object(admin.mongo_store, "get_db", return_value=None),
            patch.object(admin.mongo_store, "ready", return_value=True),
            patch.object(admin.mongo_store, "seed_rule_structures", return_value=0),
            patch.object(admin.mongo_store, "list_rule_structures", return_value=[self.rule_row]),
            patch.object(admin.mongo_store, "rule_structure", side_effect=lambda domain: self.rule_row if domain == "example.test" else None),
            patch.object(admin.mongo_store, "save_rule_structure", side_effect=save_rule),
            patch.object(admin.mongo_store, "record_rule_event"),
        ]
        for item in self.patches:
            item.start()
        admin.login_rate_limiter.reset()
        self.client = TestClient(admin.app)

    def login(self) -> None:
        response = self.client.post("/api/auth/login", json={"password": "admin"})
        self.assertEqual(response.status_code, 200)

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        admin.login_rate_limiter.reset()
        self.temp.cleanup()

    def test_login_failure_and_rate_limit(self) -> None:
        for _ in range(admin.login_rate_limiter.max_attempts):
            response = self.client.post("/api/auth/login", json={"password": "wrong"})
            self.assertEqual(response.status_code, 401)

        response = self.client.post("/api/auth/login", json={"password": "wrong"})
        self.assertEqual(response.status_code, 429)

    def test_mutation_guard_rejects_missing_session(self) -> None:
        response = self.client.patch("/api/extraction/rules/example.test", json={
            "target": "listing",
            "fields": self.rule["listing"]["fields"],
            "expected_version": self.rule_row["version"],
        })
        self.assertEqual(response.status_code, 401)

    def test_admin_read_routes_require_session(self) -> None:
        protected_routes = [
            "/api/dashboard/stats",
            "/api/sources",
            "/api/products/search",
            "/api/jobs",
            "/api/extraction/rules",
            "/api/extraction/raw-artifacts",
            "/api/dedup/candidates",
        ]
        for route in protected_routes:
            self.assertEqual(self.client.get(route).status_code, 401, route)

    def test_removed_automation_routes_are_not_exposed(self) -> None:
        self.assertEqual(self.client.post("/api/etl/trigger").status_code, 404)
        self.assertEqual(self.client.post("/api/collect/monthly").status_code, 404)
        self.assertEqual(self.client.post("/api/browser/launch").status_code, 404)

    def test_rule_patch_uses_raw_artifact_and_saves_mongo_rule(self) -> None:
        self.login()
        rule = self.client.get("/api/extraction/rules/example.test", params={"target": "listing"}).json()
        self.assertEqual(rule["preview"][0]["sample"], "Milk")
        artifact_id = rule["raw_page"]["id"]
        patched_fields = [{**rule["fields"][0], "selector": ".missing"}]
        response = self.client.patch("/api/extraction/rules/example.test", json={
            "target": "listing",
            "fields": patched_fields,
            "expected_version": rule["version"],
            "raw_artifact_id": artifact_id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.rule_row["structure"]["listing"]["fields"][0]["selector"], ".missing")
        self.assertEqual(json.loads(self.rule_path.read_text(encoding="utf-8"))["listing"]["fields"][0]["selector"], "h3")

    def test_rule_patch_rejects_version_conflict(self) -> None:
        self.login()
        rule = self.client.get("/api/extraction/rules/example.test", params={"target": "listing"}).json()
        response = self.client.patch("/api/extraction/rules/example.test", json={
            "target": "listing",
            "fields": rule["fields"],
            "expected_version": "stale-version",
        })

        self.assertEqual(response.status_code, 409)

    def test_source_crud_routes_use_mongo_store(self) -> None:
        self.login()
        source = {
            "id": "source-1",
            "name": "Example",
            "url": "https://example.test",
            "type": "E-commerce",
            "category": "Sữa",
            "note": "seed",
        }
        with patch.object(admin.mongo_store, "create_source", return_value=source) as create_source:
            response = self.client.post("/api/sources", json={
                "name": "Example",
                "url": "https://example.test",
                "type": "E-commerce",
                "category": "Sữa",
                "note": "seed",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "source-1")
        create_source.assert_called_once()

        with patch.object(admin.mongo_store, "update_source", return_value={**source, "note": "updated"}) as update_source:
            response = self.client.put("/api/sources/source-1", json={
                "name": "Example",
                "url": "https://example.test",
                "type": "E-commerce",
                "category": "Sữa",
                "note": "updated",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["note"], "updated")
        update_source.assert_called_once()

        with patch.object(admin.mongo_store, "delete_source", return_value=True) as delete_source:
            response = self.client.delete("/api/sources/source-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "deleted")
        delete_source.assert_called_once_with("source-1")

    def test_source_discovery_returns_raw_artifacts_and_rule_state(self) -> None:
        self.login()
        with patch.object(admin.mongo_store, "list_sources", return_value=[{
            "id": "source-1",
            "name": "Example",
            "url": "https://example.test",
            "domain": "example.test",
            "type": "E-commerce",
            "category": "Sữa",
        }]):
            response = self.client.get("/api/sources/source-1/discovery")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["domain"], "example.test")
        self.assertTrue(payload["summary"]["has_recent_raw"])
        self.assertTrue(payload["summary"]["has_rule"])
        self.assertEqual(payload["raw_artifacts"][0]["filename"], "task-1.mhtml")
        self.assertIn("listing", payload["rule"]["targets"])

    def test_raw_artifact_detail_returns_limited_preview(self) -> None:
        self.login()
        discovery = self.client.get("/api/extraction/raw-artifacts", params={"domain": "example.test"}).json()
        artifact_id = discovery[0]["id"]

        response = self.client.get(f"/api/extraction/raw-artifacts/{artifact_id}", params={"domain": "example.test"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["raw_page"]["filename"], "task-1.mhtml")
        self.assertIn("Milk", payload["text_preview"])
        self.assertLessEqual(len(payload["html_excerpt"]), 4000)
        self.assertGreater(payload["content_length"], 0)

    def test_dedup_queue_tracks_status(self) -> None:
        self.login()
        self.patches.append(patch.object(admin.mongo_store, "update_dedup_candidate", return_value=True))
        self.patches[-1].start()
        candidates = self.client.get("/api/dedup/candidates").json()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["status"], "pending")
        candidate_id = candidates[0]["id"]
        response = self.client.post(
            f"/api/dedup/candidates/{candidate_id}/decision",
            json={"status": "merged"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["queue_status"], "merged")

    def test_ready_reports_mongo_failure(self) -> None:
        with patch.object(admin.mongo_store, "ready", return_value=False):
            self.assertEqual(self.client.get("/api/ready").status_code, 503)

    def test_jobs_prefer_mongo_raw_pages(self) -> None:
        with patch.object(admin.mongo_store, "jobs", return_value=[{
            "id": "mongo-task",
            "filename": "mongo-task.mhtml",
            "source": "queue.example",
            "status": "Processing",
            "timestamp": datetime(2026, 5, 22, 1, 2, 3),
        }]):
            jobs = asyncio.run(admin.get_jobs())

        self.assertEqual(jobs[0]["status"], "Processing")
        self.assertEqual(jobs[0]["source"], "queue.example")
        self.assertEqual(jobs[0]["id"], "mongo-task")

    def test_market_stats_come_from_mongo_store(self) -> None:
        expected = {"avg_price": 180000, "currency": "VND", "trend": "+20.0% (2026-04 -> 2026-05)"}
        with patch.object(admin.mongo_store, "market_stats", return_value=expected):
            stats = admin._market_stats()

        self.assertEqual(stats["avg_price"], 180000)
        self.assertEqual(stats["trend"], "+20.0% (2026-04 -> 2026-05)")

    def test_source_price_comparison_uses_product_data(self) -> None:
        with patch.object(admin.mongo_store, "list_products", return_value=[
            {"source": "a.test", "price_numeric": 100},
            {"source": "a.test", "price_numeric": 300},
            {"source": "b.test", "price_numeric": 500},
            {"source": "b.test", "price_numeric": 0},
        ]):
            comparison = admin.mongo_store.source_price_comparison()

        self.assertEqual(comparison, [
            {"source": "a.test", "avg_price": 200, "count": 2},
            {"source": "b.test", "avg_price": 500, "count": 1},
        ])

    def test_raw_page_html_reads_gridfs_content(self) -> None:
        store = AdminMongoStore()
        fake_gridfs_file = Mock()
        fake_gridfs_file.read.return_value = b"<html>from gridfs</html>"
        fake_gridfs = Mock()
        fake_gridfs.get.return_value = fake_gridfs_file

        with patch.object(store, "get_db", return_value=object()), patch("apps.admin_center.backend.mongo_store.GridFS", return_value=fake_gridfs):
            html = store.raw_page_html({"raw_page_id": "raw-1", "gridfs_file_id": "file-1"})

        self.assertEqual(html, "<html>from gridfs</html>")
        fake_gridfs.get.assert_called_once_with("file-1")

    def test_production_config_rejects_default_admin_secret(self) -> None:
        config = Settings(
            ENV="production",
            ADMIN_PASSWORD="admin",
            ADMIN_SESSION_SECRET="dev-admin-session-secret",
        )
        with self.assertRaisesRegex(RuntimeError, "ADMIN_PASSWORD"):
            config.validate_production_config()

    def test_production_config_accepts_strong_admin_secret(self) -> None:
        config = Settings(
            ENV="production",
            ADMIN_PASSWORD="not-default",
            ADMIN_SESSION_SECRET="a-strong-session-secret-with-32-chars",
        )
        config.validate_production_config()


if __name__ == "__main__":
    unittest.main()
