import json
import logging
from typing import Dict, Any, List
from playwright.async_api import Page, Response

log = logging.getLogger(__name__)

class APIInterceptorBehavior:
    """
    [SOLID: S - Single Responsibility]
    Nhiệm vụ duy nhất: Lắng nghe và gạn lọc gói tin JSON từ luồng mạng Playwright.
    KHÔNG quan tâm việc mở trình duyệt, cấu hình xoay proxy hay tạo Page.
    """

    def __init__(self):
        self.captured_apis: List[Dict[str, Any]] = []

    async def _handle_response(self, response: Response):
        """Callback phân tích tĩnh từng gói tin."""
        try:
            if response.request.resource_type not in ["fetch", "xhr"]:
                return
                
            url = response.request.url
            keywords = ["api", "graphql", "products", "search", "items", "catalog", "getlist", "productlist"]
            if not any(k in url.lower() for k in keywords):
                return

            if response.status != 200:
                return
                
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    data = await response.json()
                    data_str = json.dumps(data)
                    
                    if "price" in data_str.lower() or "price_numeric" in data_str.lower() or "sku" in data_str.lower():
                        log.info(f"🔥 [API BEHAVIOR] BẮT ĐƯỢC API SẢN PHẨM: {url[:100]}...")
                        self.captured_apis.append({
                            "url": url,
                            "method": response.request.method,
                            "payload": data
                        })
                except Exception:
                    pass
        except Exception:
            pass

    def attach(self, page: Page):
        """
        [SOLID: D - Dependency Inversion]
        Nhận vào Interface `Page` từ bên ngoài truyền vào, tự động gắn móc (hook) vào mạng.
        """
        log.info("🔌 Đã gắn Plugin 'Đánh chặn API' vào trình duyệt.")
        page.on("response", self._handle_response)
        
    def get_results(self) -> List[Dict[str, Any]]:
        """Trả về dữ liệu đã thu thập được."""
        return self.captured_apis

