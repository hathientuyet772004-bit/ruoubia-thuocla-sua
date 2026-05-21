from __future__ import annotations

import json
import logging
import time
from typing import Dict, Any, Optional

import google.generativeai as genai
from shared.config import settings

log = logging.getLogger("etl.normalizer")

class ProductNormalizer:
    """
    Sử dụng Gemini AI để chuẩn hóa dữ liệu từ tầng Silver sang Gold.
    Tác vụ: Làm sạch tên, tách đơn vị, trích xuất thương hiệu và phân loại.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        
        if not self.api_key:
            log.warning("⚠️  GEMINI_API_KEY không tồn tại. Normalizer sẽ chạy ở chế độ Passthrough.")
            self.model = None
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)

    def normalize(self, raw_name: str, raw_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Gửi dữ liệu thô cho Gemini để chuẩn hóa thành schema Gold chuẩn.
        """
        if not self.model or settings.USE_MOCK_MODE:
            # Fallback đơn giản nếu không có AI
            return {
                "clean_name": raw_name.strip(),
                "brand": "Unknown",
                "unit": "N/A",
                "volume_value": None,
                "volume_unit": None,
                "pack_size": 1,
                "category": "General",
                "is_promotion": False
            }

        prompt = f"""
        Bạn là chuyên gia phân tích dữ liệu thị trường ngành hàng tiêu dùng (FMCG).
        Hãy phân tích tên sản phẩm sau và trích xuất thông tin có cấu trúc.
        
        Tên sản phẩm gốc: "{raw_name}"
        Giá gốc (nếu có): {raw_price}

        Yêu cầu trả về duy nhất 1 đối tượng JSON với các khóa sau:
        1. "clean_name": Tên sản phẩm đã làm sạch (bỏ các từ quảng cáo, ký hiệu rác).
        2. "brand": Thương hiệu của sản phẩm (ví dụ: Heineken, Vinamilk, Chivas).
        3. "unit_type": Loại bao bì (Lon, Chai, Gói, Hộp, Thùng).
        4. "volume_value": Giá trị dung tích/khối lượng số (ví dụ: 330, 0.75, 900). 
        5. "volume_unit": Đơn vị (ml, l, g, kg).
        6. "pack_size": Số lượng trong 1 thùng/lốc (ví dụ: Thùng 24 lon thì pack_size=24, mặc định là 1).
        7. "standard_category": Danh mục chuẩn của hệ thống (Bia, Rượu Vang, Rượu Mạnh, Sữa Bột, Sữa Tươi, Thuốc Lá).
        
        Trả về JSON thuần túy:
        """

        try:
            t0 = time.perf_counter()
            response = self.model.generate_content(prompt)
            elapsed = round(time.perf_counter() - t0, 2)
            
            text = response.text.strip()
            # Làm sạch JSON nếu AI trả về kèm markdown
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()

            data = json.loads(text)
            log.info(f"✅ Normalized: '{raw_name}' -> '{data.get('clean_name')}' ({elapsed}s)")
            return data
            
        except Exception as e:
            log.error(f"❌ Normalization failed for '{raw_name}': {e}")
            
            # --- Expanded Heuristic Fallback (SOLID: Open/Closed Principle) ---
            brand = "Unknown"
            category = "Uncategorized"
            low_name = raw_name.lower()
            
            # Dictionary mapping brands to potential keywords
            brand_map = {
                "Vinamilk": ["vinamilk", "dielac", "optimum"],
                "Abbott": ["abbott", "similac", "ensure", "pediasure"],
                "Nutifood": ["nutifood", "grow plus", "varna"],
                "Heineken": ["heineken", "ken bạc", "ken xanh"],
                "Tiger": ["tiger", "tiger crystal"],
                "Sài Gòn": ["bia sài gòn", "bia sai gon", "sabeco"],
                "Hà Nội": ["bia hà nội", "habeco"],
                "Chivas": ["chivas 12", "chivas 18", "chivas 21"],
                "Macallan": ["macallan"],
                "Hennessy": ["hennessy"],
                "Johnnie Walker": ["johnnie walker", "black label", "red label"],
                "Marlboro": ["marlboro"],
                "Thăng Long": ["thăng long", "thang long"],
                "Thanh Hóa": ["thanh hóa", "thanh hoa"],
                "Sài Gòn": ["thuốc lá sài gòn", "saigon bạc"],
                "555": ["ba số", "555"],
                "Essen": ["essen"],
            }
            
            for b_name, keywords in brand_map.items():
                if any(k in low_name for k in keywords):
                    brand = b_name
                    break
            
            # Logic phân loại mở rộng
            if any(k in low_name for k in ["sữa", "milk", "bột", "dinh dưỡng"]): category = "Sữa"
            elif any(k in low_name for k in ["rượu", "wine", "vang", "whisky", "vodka", "cognac"]): category = "Rượu"
            elif any(k in low_name for k in ["bia", "beer", "draught"]): category = "Bia"
            elif any(k in low_name for k in ["thuốc lá", "cigarette", "xì gà", "cigar", "bao"]): category = "Thuốc Lá"

            return {
                "clean_name": raw_name,
                "brand": brand,
                "standard_category": category,
                "error": str(e)
            }

# Ví dụ tích hợp vào ETL flow
if __name__ == "__main__":
    # Test mẫu
    normalizer = ProductNormalizer()
    
    test_items = [
        "Bia Heineken Silver Lon 330ml - Thùng 24 lon",
        "Sữa bột Vinamilk Optimum Gold 4 850g (cho trẻ 2-6 tuổi)",
        "Rượu Vang Pháp Chateau Meillier Bordeaux Superieur 750ml"
    ]
    
    print("🚀 Đang thử nghiệm chuẩn hóa dữ liệu Silver -> Gold:\n")
    for item in test_items:
        result = normalizer.normalize(item)
        print(f"Input: {item}")
        print(f"Output: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print("-" * 30)
