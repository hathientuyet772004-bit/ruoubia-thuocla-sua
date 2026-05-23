from __future__ import annotations

import unittest
from pathlib import Path


class AdminCenterFrontendRouteSmokeTests(unittest.TestCase):
    def test_route_shell_keeps_operational_pages_mounted(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        routes = [
            "/dashboard",
            "/sources",
            "/runs",
            "/products",
            "/extraction/rules",
            "/dedup",
        ]
        for route in routes:
            self.assertIn(route, app)

    def test_route_module_exports_detail_surfaces(self) -> None:
        root = Path(__file__).resolve().parents[1]
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        for page in ["SourceDetailPage", "RunDetailPage", "ExtractionRulesPage", "TaskRawPage", "DedupPage"]:
            self.assertIn(f"export function {page}", routes)

    def test_frontend_mount_and_demo_labels_are_explicit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        main = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "main.jsx").read_text(encoding="utf-8")
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        self.assertIn("ReactDOM.createRoot", main)
        self.assertIn("document.getElementById('root')", main)
        self.assertIn("demoDiscoveryRows", routes)
        self.assertIn("Xem trước phát hiện (demo)", routes)

    def test_list_routes_reject_non_json_list_responses(self) -> None:
        root = Path(__file__).resolve().parents[1]
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        api_client = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "apiClient.js").read_text(encoding="utf-8")
        self.assertIn("export function expectApiList", api_client)
        self.assertIn("fetchApiList('/sources')", routes)
        self.assertIn("fetchApiList('/jobs')", routes)


if __name__ == "__main__":
    unittest.main()
