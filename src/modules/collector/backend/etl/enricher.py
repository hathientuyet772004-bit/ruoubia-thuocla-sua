from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional

import google.generativeai as genai
from shared.config import settings
from shared.services.ocr_service import OCRService

log = logging.getLogger("etl.enricher")

class ProductEnricher:
    """
    Sử dụng Gemini AI để trích xuất các thuộc tính ẩn từ mô tả sản phẩm (Description) 
    và OCR từ hình ảnh sản phẩm (Scenario 14).
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key or settings.USE_MOCK_MODE:
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        
        # Scenario 14: OCR Integration
        self.ocr_service = OCRService(api_key=self.api_key)

    def enrich(self, category: str, description: Optional[str] = None, image_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Trích xuất các trường dữ liệu đặc thù dựa trên danh mục và hình ảnh.
        """
        results = {}

        # 1. Enrichment từ Text Description
        if self.model and description:
            try:
                results.update(self._enrich_from_text(category, description))
            except Exception as e:
                log.error(f"Text enrichment failed: {e}")

        # 2. Enrichment từ Image OCR (Scenario 14)
        # Chỉ chạy OCR nếu image_url tồn tại VÀ (thiếu info quan trọng hoặc force_ocr)
        if image_url:
            important_missing = not results.get("alcohol_content") and not results.get("detected_price")
            if important_missing:
                log.info(f"🔍 Crucial info missing. Triggering OCR for {image_url}")
                try:
                    ocr_data = self.ocr_service.process_product_image(image_url)
                    # Merge OCR metrics into results
                    results["ocr_data"] = ocr_data
                    if ocr_data.get("detected_price"): results["price_ocr"] = ocr_data["detected_price"]
                    if ocr_data.get("detected_volume"): results["volume_ocr"] = ocr_data["detected_volume"]
                    if ocr_data.get("warnings"): results["compliance_warnings"] = ocr_data["warnings"]
                except Exception as e:
                    log.error(f"Image OCR enrichment failed: {e}")

        return results

    def _enrich_from_text(self, category: str, description: str) -> Dict[str, Any]:
        prompt = f"""
        Bạn là chuyên gia về dữ liệu sản phẩm ngành {category}.
        Hãy trích xuất các thuộc tính kỹ thuật từ văn bản mô tả sau.
        
        Mô tả: "{description[:2000]}"

        Yêu cầu trả về JSON với các trường (chỉ trả về trường có thông tin):
        - Nếu là Rượu: "vintage", "grape_variety", "alcohol_content", "region", "sweetness".
        - Nếu là Sữa: "age_group", "origin", "main_ingredients", "expiry_period".
        - Nếu là Thuốc lá: "nicotine_content", "tar_content", "origin".
        
        Nếu không có thông tin, trả về {{}}. Trả về JSON thuần túy:
        """
        response = self.model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        return json.loads(text)

if __name__ == "__main__":
    enricher = ProductEnricher()
    desc = "Rượu vang đỏ Chateau Meillier niên vụ 2018, vùng Bordeaux Pháp, nồng độ 14%."
    img = "https://winemart.vn/wp-content/uploads/2021/05/chateau-meillier-bordeaux-superieur.jpg"
    
    print("🚀 Testing Hybrid Enrichment (Text + OCR):")
    res = enricher.enrich("Rượu Vang", desc, img)
    print(json.dumps(res, indent=2, ensure_ascii=False))

