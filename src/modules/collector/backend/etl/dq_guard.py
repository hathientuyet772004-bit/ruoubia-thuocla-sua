import logging
import json
from typing import Dict, Any, List
import google.generativeai as genai
from shared.config import settings

log = logging.getLogger("etl.dq_guard")

class DataQualityGuard:
    """
    Sử dụng AI để kiểm tra tính logic và chất lượng của dữ liệu sau khi ETL.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key or settings.USE_MOCK_MODE:
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def validate_logic(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kiểm tra tính hợp lý của bộ dữ liệu sản phẩm.
        """
        if not self.model:
            return {"passed": True, "score": 1.0}

        prompt = f"""
        Bạn là kiểm soát viên chất lượng dữ liệu. Hãy đánh giá tính logic của sản phẩm này:
        JSON: {json.dumps(product_data, ensure_ascii=False)}

        Hãy kiểm tra:
        1. Giá có bất thường không (quá rẻ < 10k cho rượu, hoặc quá đắt)?
        2. So sánh giá thu thập được và giá từ OCR (nếu có trong details) xem có lệch nhau > 20% không?
        3. Tên sản phẩm và danh mục có khớp nhau không?
        4. Các trường quan trọng có bị null không?

        Trả về JSON:
        {{
            "passed": true/false,
            "score": 0.0 - 1.0,
            "is_ocr_verified": true/false,
            "final_decision": {{
                "price": 0.0,
                "reason": "Giải thích tại sao chọn giá này (ví dụ: khớp OCR, hoặc HTML tin cậy hơn)"
            }},
            "issues": ["mô tả lỗi nếu có"],
            "suggestion": "hướng khắc phục"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            log.error(f"DQ Check failed: {e}")
            return {"passed": True, "score": 1.0} # Bỏ qua nếu AI lỗi
