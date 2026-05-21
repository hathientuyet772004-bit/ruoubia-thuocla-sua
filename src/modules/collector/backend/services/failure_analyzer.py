import logging
import json
import google.generativeai as genai
from core.config import settings

log = logging.getLogger("service.failure_analyzer")

class FailureAnalyzer:
    """
    Sử dụng AI để chẩn đoán nguyên nhân thất bại của Crawler.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key or settings.USE_MOCK_MODE:
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def analyze_failure(self, domain: str, html_snippet: str, error_msg: str) -> dict:
        """
        Phân tích HTML snippet để tìm nguyên nhân lỗi.
        """
        if not self.model:
            return {"error": "AI Model not configured"}

        prompt = f"""
        Hệ thống crawl dữ liệu tại website {domain} bị lỗi.
        Lỗi kỹ thuật: {error_msg}
        
        Nội dung HTML (một phần):
        ---
        {html_snippet[:3000]}
        ---

        Hãy chẩn đoán nguyên nhân thất bại:
        1. Có phải do website đổi giao diện (class CSS thay đổi) không?
        2. Có phải bị chặn bởi Captcha/Cloudflare không?
        3. Trang web có báo "Hết hàng" hay "Không tìm thấy sản phẩm" không?
        4. Hãy đề xuất CSS selector mới (nếu thấy) cho Name và Price.

        Trả về JSON:
        {{
            "diagnosis": "nguyên nhân tóm tắt",
            "is_structural_change": true/false,
            "is_blocked": true/false,
            "is_out_of_stock": true/false,
            "new_selectors": {{"name": "...", "price": "..."}},
            "action_required": "tiếp tục chạy hay cần con người can thiệp"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        except Exception as e:
            log.error(f"Failure analysis failed: {e}")
            return {"diagnosis": "Could not analyze failure via AI"}

if __name__ == "__main__":
    analyzer = FailureAnalyzer()
    # Giả lập HTML bị chặn
    sample_html = "<html><head><title>Access Denied</title></head><body><h1>403 Forbidden</h1><p>Cloudflare Ray ID: ...</p></body></html>"
    print(json.dumps(analyzer.analyze_failure("test.com", sample_html, "Status 403"), indent=2))
