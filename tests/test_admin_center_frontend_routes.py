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
            "/collection",
            "/gen-data",
            "/runs",
            "/products",
            "/extraction/rules",
        ]
        for route in routes:
            self.assertIn(route, app)

    def test_route_module_exports_detail_surfaces(self) -> None:
        root = Path(__file__).resolve().parents[1]
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        for page in ["SourceDetailPage", "PipelinesPage", "GenDataPage", "RunDetailPage", "ExtractionRulesPage", "TaskRawPage"]:
            self.assertIn(f"default as {page}", routes)

    def test_frontend_mount_and_source_discovery_are_wired(self) -> None:
        root = Path(__file__).resolve().parents[1]
        main = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "main.jsx").read_text(encoding="utf-8")
        app = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        route_shell = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "routeShell.jsx").read_text(encoding="utf-8")
        dashboard = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
        rule_review_page = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "RuleReviewPage.jsx").read_text(encoding="utf-8")
        pages = "\n".join(path.read_text(encoding="utf-8") for path in (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages").glob("*.jsx"))
        self.assertIn("ReactDOM.createRoot", main)
        self.assertIn("document.getElementById('root')", main)
        self.assertNotIn("AdminLogin", app)
        self.assertNotIn("/api/auth/session", app)
        self.assertIn("/collection", app)
        self.assertIn("/gen-data", app)
        self.assertIn("PipelinesPage", routes)
        self.assertIn("Prompt tạo dữ liệu", pages)
        self.assertIn("/sources/generation-prompt/latest", pages)
        self.assertIn("/sources/synthetic-batches?limit=80", pages)
        self.assertIn("Array.isArray(resource.data) ? resource.data : []", pages)
        self.assertNotIn("resource.data?.pipelines || []", pages)
        self.assertIn("last_run_status || pipeline.status", pages)
        self.assertIn("grounded_synthetic", pages)
        self.assertNotIn("Tính năng đang được xây dựng", pages)
        self.assertIn("Gen dữ liệu thay thế", pages)
        self.assertIn("Pipeline mới", pages)
        self.assertIn("Có trang thô", pages)
        self.assertIn("Trong kho giá", pages)
        self.assertIn("Cần rà soát", pages)
        self.assertIn("quarantine_count", pages)
        self.assertIn("/pipelines/runs?limit=80", pages)
        self.assertIn("Lượt chạy pipeline", pages)
        self.assertIn("Tác vụ trang thô", pages)
        self.assertIn("Pipeline bị chặn", pages)
        self.assertIn("<ExtractionRulesPage navigate={navigate} />", app)
        self.assertIn("Cảnh báo selector", pages)
        self.assertIn("Trường bắt buộc", pages)
        self.assertIn("Duyệt Rule AI", pages)
        self.assertIn("status=${status}&limit=200", pages)
        self.assertIn("'validated', 'Có thể duyệt'", pages)
        self.assertIn("Có thể duyệt", pages)
        self.assertIn("đạt quality gate", pages)
        self.assertNotIn("useState('pending')", rule_review_page)
        self.assertNotIn("setStatus('pending')", rule_review_page)
        self.assertNotIn("Mật khẩu quản trị", app)
        self.assertIn("/sources/${sourceId}/discovery", pages)
        self.assertIn("/sources/${sourceId}/collect", pages)
        self.assertIn("/sources/${sourceId}/runs?limit=12", pages)
        self.assertIn("waitForLatestSourceRun", pages)
        self.assertIn("đang kiểm tra kết quả lượt chạy", pages)
        self.assertIn("raw_artifacts", pages)
        self.assertIn("products_written", pages)
        self.assertIn("/sources/template", pages)
        self.assertIn("/sources/import", pages)
        self.assertIn("/sources/export", pages)
        self.assertIn("/products/export", pages)
        self.assertIn("store: store || undefined", pages)
        self.assertNotIn("/stores/search", pages)
        self.assertNotIn("/stores/export", pages)
        self.assertNotIn("StoresPage", routes)
        self.assertNotIn("AiReviewPage", routes)
        self.assertNotIn("DedupPage", routes)
        self.assertNotIn("/ai/review", app)
        self.assertNotIn("/dedup", app)
        self.assertNotIn("AI duyệt", route_shell)
        self.assertNotIn("Rà soát trùng lặp", route_shell)
        self.assertNotIn("AI Review", dashboard)
        self.assertNotIn("Dedup", dashboard)
        self.assertIn("/extraction/ai/analyze", pages)
        self.assertIn("Phân tích bằng Gemini", pages)
        self.assertIn("Kết quả Gemini", pages)
        self.assertIn("Trang thô", pages)
        self.assertIn("Hệ thống OK", pages)
        self.assertIn("PIPELINE_STAGES_DEF", pages)
        self.assertIn("allCandidates", pages)
        self.assertIn("visibleCandidates", pages)
        self.assertIn("tổng queue", pages)
        self.assertIn("store_address", pages)
        self.assertIn("viewMode", pages)
        self.assertIn("ProductRows products={products}", pages)
        self.assertIn("ProductList products={products}", pages)
        self.assertIn("Mẫu thêm nguồn", pages)
        self.assertIn("Tải lên danh sách", pages)
        self.assertIn("Tải xuống danh sách", pages)
        self.assertIn("Tải CSV", pages)
        self.assertIn("Tính lại ứng viên", pages)
        self.assertIn("Chạy thu thập", pages)
        self.assertIn("Lịch sử thu thập", pages)
        self.assertIn("Bảng", pages)
        self.assertIn("Danh sách", pages)
        self.assertIn("/extraction/raw-artifacts/${selectedArtifact.id}", pages)
        self.assertIn("Phát hiện dữ liệu", pages)
        self.assertIn("Xem trước trang thô", pages)
        self.assertNotIn("demoDiscoveryRows", pages)
        self.assertNotIn("Xem trước phát hiện (demo)", pages)

    def test_list_routes_reject_non_json_list_responses(self) -> None:
        root = Path(__file__).resolve().parents[1]
        routes = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages" / "adminRoutes.jsx").read_text(encoding="utf-8")
        pages = "\n".join(path.read_text(encoding="utf-8") for path in (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "pages").glob("*.jsx"))
        api_client = (root / "src" / "apps" / "admin_center" / "frontend" / "src" / "apiClient.js").read_text(encoding="utf-8")
        self.assertIn("export function expectApiList", api_client)
        self.assertIn("fetchApiList('/sources')", pages)
        self.assertIn("fetchApiList('/jobs?limit=80')", pages)


if __name__ == "__main__":
    unittest.main()

