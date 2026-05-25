from __future__ import annotations

import json
import tempfile
import unittest
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import main as admin
from apps.admin_center.backend import gemini_service
from apps.admin_center.backend import extraction_writer
from apps.admin_center.backend import pipeline_service
from apps.admin_center.backend import worker
from apps.admin_center.backend.cache import dashboard_cache, product_cache, source_cache, store_cache
from apps.admin_center.backend.mongo_store import AdminMongoStore
from apps.admin_center.backend.settings import Settings
from apps.admin_center.backend import store_service


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
        dashboard_cache.clear()
        product_cache.clear()
        source_cache.clear()
        store_cache.clear()
        admin.login_rate_limiter.reset()
        self.client = TestClient(admin.app)

    def login(self) -> None:
        response = self.client.post("/api/auth/login", json={"password": "admin"})
        self.assertEqual(response.status_code, 200)

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        dashboard_cache.clear()
        product_cache.clear()
        source_cache.clear()
        store_cache.clear()
        admin.login_rate_limiter.reset()
        self.temp.cleanup()

    def test_login_failure_and_rate_limit(self) -> None:
        for _ in range(admin.login_rate_limiter.max_attempts):
            response = self.client.post("/api/auth/login", json={"password": "wrong"})
            self.assertEqual(response.status_code, 401)

        response = self.client.post("/api/auth/login", json={"password": "wrong"})
        self.assertEqual(response.status_code, 429)

    def test_mutation_guard_requires_mongo_ready(self) -> None:
        with patch.object(admin.mongo_store, "ready", return_value=False):
            response = self.client.patch("/api/extraction/rules/example.test", json={
                "target": "listing",
                "fields": self.rule["listing"]["fields"],
                "expected_version": self.rule_row["version"],
            })
        self.assertEqual(response.status_code, 503)

    def test_admin_read_routes_are_internal_without_session(self) -> None:
        response = self.client.get("/api/extraction/raw-artifacts", params={"domain": "example.test"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["filename"], "task-1.mhtml")

    def test_mutation_routes_are_internal_without_session(self) -> None:
        response = self.client.patch("/api/extraction/rules/example.test", json={
            "target": "listing",
            "fields": self.rule["listing"]["fields"],
            "expected_version": self.rule_row["version"],
        })
        self.assertEqual(response.status_code, 200)

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

    def test_source_collect_endpoint_runs_internal_pipeline(self) -> None:
        pipeline = {"id": "source-source-1", "pipeline_id": "source-source-1", "entry_urls": ["https://example.test"]}
        run = {"run_id": "run-1", "pipeline_id": "source-source-1", "status": "completed", "summary": {"raw_artifacts": 1}}
        with patch.object(pipeline_service, "ensure_source_pipeline", return_value=pipeline) as ensure_pipeline, \
            patch.object(worker, "capture_entry_urls", return_value=[{"raw_page_id": "raw-1"}]) as capture_entry_urls, \
            patch.object(pipeline_service, "run_pipeline", return_value=run) as run_pipeline:
            response = self.client.post("/api/sources/source-1/collect")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")
        self.assertEqual(response.json()["pipeline_id"], "source-source-1")
        ensure_pipeline.assert_called_once_with("source-1")
        capture_entry_urls.assert_called_once_with(pipeline)
        run_pipeline.assert_called_once_with("source-source-1")

    def test_source_runs_endpoint_returns_pipeline_runs_for_source(self) -> None:
        with patch.object(pipeline_service, "list_source_runs", return_value=[{
            "id": "run-1",
            "run_id": "run-1",
            "pipeline_id": "source-source-1",
            "status": "completed",
        }]) as list_runs:
            response = self.client.get("/api/sources/source-1/runs", params={"limit": 5})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "run-1")
        list_runs.assert_called_once_with("source-1", 5)

    def test_pipeline_routes_support_no_code_management(self) -> None:
        self.login()
        pipeline = {
            "id": "pipe-1",
            "pipeline_id": "pipe-1",
            "name": "Hybrid AI",
            "mode": "hybrid",
            "source_ids": ["source-1"],
            "target_hints": ["product_listing"],
            "schema_mode": "auto",
            "enabled": True,
            "source_count": 1,
            "run_count": 0,
            "last_run_at": None,
        }
        run = {
            "id": "run-1",
            "run_id": "run-1",
            "pipeline_id": "pipe-1",
            "pipeline_name": "Hybrid AI",
            "mode": "hybrid",
            "status": "completed",
            "summary": {
                "source_count": 1,
                "processed_sources": 1,
                "raw_artifacts": 1,
                "ai_attempts": 1,
                "ai_accepted": 1,
                "warnings": [],
                "results": [],
            },
        }
        with patch.object(pipeline_service, "pipeline_overview", return_value={"total": 1, "enabled": 1, "runs": 1, "running": 0}), \
            patch.object(pipeline_service, "list_pipelines", return_value=[pipeline]), \
            patch.object(pipeline_service, "list_pipeline_templates", return_value=[{"template_id": "hybrid-ai", "name": "Hybrid AI"}]), \
            patch.object(pipeline_service, "list_pipeline_runs", return_value=[run]), \
            patch.object(pipeline_service, "create_pipeline", return_value=pipeline), \
            patch.object(pipeline_service, "update_pipeline", return_value={**pipeline, "notes": "updated"}), \
            patch.object(pipeline_service, "delete_pipeline", return_value=True), \
            patch.object(pipeline_service, "run_pipeline", return_value=run):
            overview = self.client.get("/api/pipelines/overview")
            listing = self.client.get("/api/pipelines")
            templates = self.client.get("/api/pipelines/templates")
            runs = self.client.get("/api/pipelines/runs")
            created = self.client.post("/api/pipelines", json={
                "name": "Hybrid AI",
                "description": "Manage pipelines without code",
                "mode": "hybrid",
                "source_ids": ["source-1"],
                "entry_urls": [],
                "search_queries": [],
                "target_hints": ["product_listing"],
                "schema_mode": "auto",
                "schedule_type": "manual",
                "cron": None,
                "page_budget": 100,
                "max_depth": 2,
                "region": "VN",
                "user_agent": "",
                "enabled": True,
                "notes": "",
            })
            updated = self.client.put("/api/pipelines/pipe-1", json={
                "name": "Hybrid AI",
                "description": "Manage pipelines without code",
                "mode": "hybrid",
                "source_ids": ["source-1"],
                "entry_urls": [],
                "search_queries": [],
                "target_hints": ["product_listing"],
                "schema_mode": "auto",
                "schedule_type": "manual",
                "cron": None,
                "page_budget": 100,
                "max_depth": 2,
                "region": "VN",
                "user_agent": "",
                "enabled": True,
                "notes": "updated",
            })
            ran = self.client.post("/api/pipelines/pipe-1/run")
            deleted = self.client.delete("/api/pipelines/pipe-1")

        self.assertEqual(overview.status_code, 200)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(templates.status_code, 200)
        self.assertEqual(runs.status_code, 200)
        self.assertEqual(created.status_code, 200)
        self.assertEqual(updated.json()["notes"], "updated")
        self.assertEqual(ran.json()["status"], "completed")
        self.assertEqual(deleted.json()["status"], "deleted")

    def test_source_template_downloads_csv_format(self) -> None:
        response = self.client.get("/api/sources/template")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("source-import-template.csv", response.headers["content-disposition"])
        self.assertIn("name,url,type,category,note", response.text)
        self.assertNotIn("exported_at", response.text)

    def test_source_import_accepts_csv_rows(self) -> None:
        created = []

        def create_source(row):
            created.append(row)
            return {"id": f"source-{len(created)}", **row}

        csv_payload = "name,url,type,category,note\nExample,https://example.test,E-commerce,Sữa,seed\n"
        with patch.object(admin.mongo_store, "create_source", side_effect=create_source):
            response = self.client.post("/api/sources/import", content=csv_payload, headers={"content-type": "text/csv"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["imported"], 1)
        self.assertEqual(created[0]["name"], "Example")
        self.assertEqual(created[0]["category"], "Sữa")

    def test_source_export_downloads_current_list_with_timestamp_filename(self) -> None:
        with patch.object(admin.mongo_store, "list_sources", return_value=[{
            "id": "source-1",
            "name": "Example",
            "url": "https://example.test",
            "type": "E-commerce",
            "category": "Sữa",
            "note": "seed",
        }]):
            response = self.client.get("/api/sources/export")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("source-list-", response.headers["content-disposition"])
        self.assertIn("Example,https://example.test,E-commerce,Sữa,seed", response.text)
        self.assertNotIn("exported_at", response.text)

    def test_product_export_downloads_price_csv(self) -> None:
        with patch.object(admin.mongo_store, "list_products", return_value=[{
            "name": "Milk",
            "price": 29000,
            "original_price": 32000,
            "currency": "VND",
            "source": "example.test",
            "category": "Sữa",
            "brand": "Example",
            "store_id": "store-1",
            "store_name": "Example Store",
            "store_url": "https://example.test/store",
            "store_address": "123 Example Street",
            "store_phone": "0900000000",
            "url": "https://example.test/p/1",
            "updated_at": "2026-05-25T01:00:00+07:00",
        }]):
            response = self.client.get("/api/products/export", params={"store": "Example Store"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("product-price-list-", response.headers["content-disposition"])
        self.assertIn("name,price,original_price,currency,source,category,brand,store_id,store_name,store_url,store_address,store_phone,url,updated_at", response.text)
        self.assertIn("Milk,29000,32000,VND,example.test,Sữa,Example,store-1,Example Store,https://example.test/store,123 Example Street,0900000000,https://example.test/p/1,2026-05-25T01:00:00+07:00", response.text)

    def test_store_search_and_export_use_store_collections(self) -> None:
        with patch.object(admin.mongo_store, "list_stores", return_value=[{
            "id": "store-1",
            "name": "Example Store",
            "source": "example.test",
            "address": "123 Example Street",
            "phone": "0900000000",
            "url": "https://example.test/store",
            "latitude": 10.1,
            "longitude": 106.1,
            "product_count": 3,
            "updated_at": "2026-05-25T01:00:00+07:00",
        }]):
            response = self.client.get("/api/stores/search")
            export = self.client.get("/api/stores/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "Example Store")
        self.assertEqual(response.json()[0]["product_count"], 3)
        self.assertEqual(export.status_code, 200)
        self.assertIn("store-list-", export.headers["content-disposition"])
        self.assertIn("name,source,address,phone,url,latitude,longitude,product_count,updated_at", export.text)
        self.assertIn("Example Store,example.test,123 Example Street,0900000000,https://example.test/store,10.1,106.1,3,2026-05-25T01:00:00+07:00", export.text)

    def test_store_search_falls_back_to_branch_outputs(self) -> None:
        output_dir = self.root / "store" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "branches.json"
        output_path.write_text(json.dumps({
            "source_site": "ruoutot.net",
            "branches": [
                {
                    "branch_name": "Ha Noi Branch",
                    "address": "12 Example Street",
                    "phone": "0900000001",
                    "url": "https://ruoutot.net/ha-noi",
                },
                {
                    "name": "Sai Gon Branch",
                    "store_address": "34 Example Avenue",
                    "store_phone": "0900000002",
                    "store_url": "https://ruoutot.net/sai-gon",
                },
            ],
        }), encoding="utf-8")

        store_cache.clear()
        rows = store_service.search_stores(q="Branch", source="all", limit=10)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source"], "ruoutot.net")
        self.assertIn("Branch", rows[0]["name"])
        self.assertEqual(rows[0]["product_count"], 0)
        self.assertTrue(rows[0]["id"].startswith("branches-"))

    def test_gemini_prompt_mentions_json_only_and_store_targets(self) -> None:
        prompt = gemini_service.build_gemini_prompt(
            domain="ruoutot.net",
            html="<html><body><h1>Title</h1><div class='store'>Branch</div></body></html>",
            url="https://ruoutot.net/",
            page_type="homepage",
            target_hint="auto",
        )
        self.assertIn("Return JSON only", prompt)
        self.assertIn('"stores"', prompt)
        self.assertIn('"product_detail"', prompt)
        self.assertIn('"listing"', prompt)

    def test_gemini_analyze_validates_extracted_selectors(self) -> None:
        self.patches.append(patch.object(gemini_service.settings, "GEMINI_API_KEY", "test-key"))
        self.patches.append(patch.object(gemini_service.settings, "GEMINI_MODEL", "gemini-2.5-flash"))
        self.patches.append(patch.object(gemini_service, "urlopen"))
        self.patches[-3].start()
        self.patches[-2].start()
        mock_urlopen = self.patches[-1].start()
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "domain": "example.test",
                            "page_type": "homepage",
                            "listing": {
                                "container_selector": "body",
                                "item_selector": "h1, .store",
                                "pagination": {
                                    "type": "none",
                                    "next_button_selector": None,
                                    "page_param": None,
                                    "url_pattern": None,
                                    "max_pages": None,
                                },
                                "fields": [
                                    {"name": "product_name", "selector": "h1", "attr": None, "required": True, "transform": "text_content"},
                                ],
                            },
                            "product_detail": {
                                "fields": [
                                    {"name": "price", "selector": "h1", "attr": None, "required": True, "transform": "text_content"},
                                ],
                            },
                            "stores": {
                                "container_selector": "body",
                                "item_selector": ".store",
                                "fields": [
                                    {"name": "store_name", "selector": ".store", "attr": None, "required": True, "transform": "text_content"},
                                ],
                            },
                            "notes": "ok",
                        })
                    }]
                }
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        response = self.client.post("/api/extraction/ai/analyze", json={
            "domain": "example.test",
            "html": "<html><body><h1>Title</h1><div class='store'>Branch</div></body></html>",
            "page_type": "homepage",
            "target_hint": "auto",
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["model"], "gemini-2.5-flash")
        self.assertTrue(payload["validation"]["accepted"])
        self.assertGreater(payload["validation"]["targets"]["listing"]["field_score"], 0)
        self.assertGreater(payload["validation"]["targets"]["stores"]["field_score"], 0)
        mock_urlopen.assert_called_once()

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
        refresh = self.client.post("/api/dedup/candidates/refresh")
        self.assertEqual(refresh.status_code, 200)
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

    def test_extraction_writer_upserts_products_offers_and_stores(self) -> None:
        fake_db = Mock()
        fake_db.sc_products.update_one = Mock()
        fake_db.sc_offers.update_one = Mock()
        fake_db.sc_stores.update_one = Mock()
        structure = {
            "domain": "example.test",
            "listing": {
                "item_selector": ".product",
                "fields": [
                    {"name": "product_name", "selector": ".name", "required": True},
                    {"name": "price", "selector": ".price", "transform": "clean_price"},
                    {"name": "product_url", "selector": "a", "attr": "href"},
                ],
            },
            "stores": {
                "item_selector": ".store",
                "fields": [
                    {"name": "store_name", "selector": ".store-name", "required": True},
                    {"name": "store_address", "selector": ".address"},
                ],
            },
        }
        html = """
        <html><body>
          <article class="product"><a href="/milk"><h3 class="name">Milk 1L</h3></a><span class="price">29.000 đ</span></article>
          <section class="store"><b class="store-name">Example Store</b><span class="address">123 Street</span></section>
        </body></html>
        """

        with patch.object(extraction_writer.deps.mongo_store, "get_db", return_value=fake_db):
            result = extraction_writer.write_extraction(
                {"id": "raw-1", "domain": "example.test", "url": "https://example.test/list"},
                html,
                structure,
                "source-1",
            )

        self.assertEqual(result["products"], 1)
        self.assertEqual(result["offers"], 1)
        self.assertEqual(result["stores"], 1)
        product_payload = fake_db.sc_products.update_one.call_args.args[1]["$set"]
        self.assertEqual(product_payload["product_name"], "Milk 1L")
        self.assertEqual(product_payload["price_numeric"], 29000)
        self.assertEqual(product_payload["product_url"], "https://example.test/milk")
        store_payload = fake_db.sc_stores.update_one.call_args.args[1]["$set"]
        self.assertEqual(store_payload["store_name"], "Example Store")
        self.assertEqual(store_payload["store_address"], "123 Street")

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

    def test_production_config_rejects_placeholder_runtime_values(self) -> None:
        config = Settings(
            ENV="production",
            MONGODB_URI="mongodb+srv://<user>:<password>@<cluster-host>/?appName=<app-name>",
            CORS_ALLOW_ORIGINS="https://your-domain.com",
        )
        with self.assertRaisesRegex(RuntimeError, "MONGODB_URI"):
            config.validate_production_config()

    def test_production_config_accepts_strong_admin_secret(self) -> None:
        config = Settings(
            ENV="production",
            ADMIN_PASSWORD="not-default",
            ADMIN_SESSION_SECRET="a-strong-session-secret-with-32-chars",
            MONGODB_URI="mongodb+srv://user:password@cluster.example.mongodb.net/app",
            CORS_ALLOW_ORIGINS="https://admin.example.com",
        )
        config.validate_production_config()

    def test_production_config_rejects_default_admin_secret_when_auth_enabled(self) -> None:
        config = Settings(
            ENV="production",
            ADMIN_AUTH_ENABLED=True,
            ADMIN_PASSWORD="admin",
            ADMIN_SESSION_SECRET="dev-admin-session-secret",
            MONGODB_URI="mongodb+srv://user:password@cluster.example.mongodb.net/app",
            CORS_ALLOW_ORIGINS="https://admin.example.com",
        )
        with self.assertRaisesRegex(RuntimeError, "ADMIN_PASSWORD"):
            config.validate_production_config()

    def test_worker_due_check_uses_interval_for_enabled_pipelines(self) -> None:
        now = datetime(2026, 5, 25, 1, 0, 0)

        self.assertTrue(worker.run_is_due({
            "enabled": True,
            "schedule_type": "manual",
            "last_run_at": datetime(2026, 5, 25, 0, 54, 0),
        }, now, 300, run_manual=True))
        self.assertFalse(worker.run_is_due({
            "enabled": True,
            "schedule_type": "manual",
            "last_run_at": datetime(2026, 5, 25, 0, 58, 0),
        }, now, 300, run_manual=True))
        self.assertFalse(worker.run_is_due({
            "enabled": True,
            "schedule_type": "manual",
            "last_run_at": None,
        }, now, 300, run_manual=False))

    def test_worker_captures_entry_urls_to_raw_page_store(self) -> None:
        fake_db = Mock()
        fake_db.admin_pipeline_worker_events.insert_one = Mock()
        saved = []

        def save_raw_page(raw_page, content):
            saved.append((raw_page, content))
            return {**raw_page, "content_length": len(content)}

        response = Mock()
        response.read.return_value = b"<html><body>Milk</body></html>"
        response.headers.get.return_value = "text/html"
        response.geturl.return_value = "https://example.test/products"
        response.status = 200
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch.object(worker.deps.mongo_store, "get_db", return_value=fake_db), \
            patch.object(worker.deps.mongo_store, "save_raw_page_content", side_effect=save_raw_page), \
            patch.object(worker, "urlopen", return_value=response):
            captured = worker.capture_entry_urls({
                "pipeline_id": "pipe-1",
                "entry_urls": ["https://example.test/products"],
                "user_agent": "TestAgent/1.0",
            })

        self.assertEqual(len(captured), 1)
        self.assertEqual(saved[0][0]["domain"], "example.test")
        self.assertEqual(saved[0][0]["url"], "https://example.test/products")
        self.assertEqual(saved[0][0]["status"], "completed")
        self.assertEqual(saved[0][1], b"<html><body>Milk</body></html>")
        fake_db.admin_pipeline_worker_events.insert_one.assert_called_once()

    def test_pipeline_writer_runs_when_gemini_is_rate_limited(self) -> None:
        fake_db = Mock()
        fake_db.admin_pipelines.find_one.return_value = {
            "pipeline_id": "source-source-1",
            "name": "Collect Source",
            "mode": "hybrid",
            "source_ids": ["source-1"],
            "target_hints": ["product_listing"],
        }
        fake_db.admin_pipeline_runs.insert_one = Mock()
        fake_db.admin_pipeline_runs.update_one = Mock()
        fake_db.admin_pipelines.update_one = Mock()
        discovery = {
            "domain": "example.test",
            "raw_artifacts": [{"id": "raw-1"}],
            "rule": {"targets": []},
        }
        with patch.object(pipeline_service.deps.mongo_store, "get_db", return_value=fake_db), \
            patch.object(pipeline_service.deps.mongo_store, "rule_structure", return_value=None), \
            patch.object(pipeline_service.source_service, "source_discovery", return_value=discovery), \
            patch.object(pipeline_service.extraction_service, "analyze_with_gemini", side_effect=HTTPException(status_code=503, detail="Gemini API request failed: 429 Too Many Requests")), \
            patch.object(pipeline_service.deps, "raw_artifact_html", return_value=({"id": "raw-1", "domain": "example.test", "url": "https://example.test"}, "<html></html>")), \
            patch.object(pipeline_service.extraction_writer, "write_extraction", return_value={"products": 1, "offers": 1, "stores": 1, "warnings": []}):
            result = pipeline_service.run_pipeline("source-source-1")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["summary"]["products_written"], 1)
        self.assertIn("Gemini skipped", result["summary"]["warnings"][0])


if __name__ == "__main__":
    unittest.main()
