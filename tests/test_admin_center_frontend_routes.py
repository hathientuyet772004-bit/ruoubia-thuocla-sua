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

    def test_frontend_mount_and_source_discovery_are_wired(self) -> None:
        root = Path(__file__).resolve().parents[1]
        main = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "main.jsx").read_text(encoding="utf-8")
        app = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        self.assertIn("ReactDOM.createRoot", main)
        self.assertIn("document.getElementById('root')", main)
        self.assertNotIn("AdminLogin", app)
        self.assertNotIn("/api/auth/session", app)
        self.assertNotIn("Mật khẩu quản trị", app)
        self.assertIn("/sources/${sourceId}/discovery", routes)
        self.assertIn("/sources/template", routes)
        self.assertIn("/sources/import", routes)
        self.assertIn("/sources/export", routes)
        self.assertIn("/products/export", routes)
        self.assertIn("viewMode", routes)
        self.assertIn("ProductRows products={products}", routes)
        self.assertIn("ProductList products={products}", routes)
        self.assertIn("Mẫu thêm nguồn", routes)
        self.assertIn("Tải lên danh sách", routes)
        self.assertIn("Tải xuống danh sách", routes)
        self.assertIn("Tải CSV", routes)
        self.assertIn("Bảng", routes)
        self.assertIn("Danh sách", routes)
        self.assertIn("/extraction/raw-artifacts/${selectedArtifact.id}", routes)
        self.assertIn("Phát hiện dữ liệu", routes)
        self.assertIn("Xem trước trang thô", routes)
        self.assertNotIn("demoDiscoveryRows", routes)
        self.assertNotIn("Xem trước phát hiện (demo)", routes)

    def test_list_routes_reject_non_json_list_responses(self) -> None:
        root = Path(__file__).resolve().parents[1]
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        api_client = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "apiClient.js").read_text(encoding="utf-8")
        self.assertIn("export function expectApiList", api_client)
        self.assertIn("fetchApiList('/sources')", routes)
        self.assertIn("fetchApiList('/jobs')", routes)


if __name__ == "__main__":
    unittest.main()
