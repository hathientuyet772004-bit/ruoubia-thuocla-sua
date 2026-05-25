from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_cli_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "batch-gemini-analyze.py"
    spec = importlib.util.spec_from_file_location("batch_gemini_analyze", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BatchGeminiCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = load_cli_module()

    def test_run_batch_uses_api_endpoints_and_keeps_errors_per_domain(self) -> None:
        calls = []

        def fake_http_json(method, url, payload=None):
            calls.append((method, url, payload))
            if url.endswith("/api/sources"):
                return [
                    {"id": "source-1", "domain": "ruoutot.net", "name": "Rượu Tốt"},
                    {"id": "source-2", "domain": "maltco.vn", "name": "Maltco"},
                ]
            if url.endswith("/api/sources/source-1/discovery"):
                return {
                    "domain": "ruoutot.net",
                    "rule": {"targets": ["listing"]},
                    "raw_artifacts": [{"id": "raw-1"}],
                }
            if url.endswith("/api/extraction/ai/analyze"):
                return {
                    "model": "gemini-2.5-flash",
                    "draft": {"domain": "ruoutot.net"},
                    "validation": {"accepted": True},
                }
            raise AssertionError(f"Unexpected URL: {url}")

        with patch.object(self.cli, "http_json", side_effect=fake_http_json):
            results = self.cli.run_batch("http://localhost", ["ruoutot.net", "missing.net"])

        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[0]["raw_artifact_id"], "raw-1")
        self.assertTrue(results[0]["accepted"])
        self.assertEqual(results[1]["status"], "error")
        self.assertEqual(results[1]["error"], "Source not found")
        self.assertTrue(any(url.endswith("/api/sources") for _, url, _ in calls))
        self.assertTrue(any(url.endswith("/api/extraction/ai/analyze") for _, url, _ in calls))

    def test_main_writes_jsonl_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "results.jsonl"
            with patch.object(self.cli, "run_batch", return_value=[{"domain": "ruoutot.net", "status": "ok"}]):
                code = self.cli.main(["--domain", "ruoutot.net", "--output", str(output_path)])

            self.assertEqual(code, 0)
            content = output_path.read_text(encoding="utf-8").strip()
            self.assertEqual(json.loads(content), {"domain": "ruoutot.net", "status": "ok"})


if __name__ == "__main__":
    unittest.main()
