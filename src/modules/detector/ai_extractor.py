"""
Gemini AI Extractor — trích xuất, chuẩn hóa và phân tích dữ liệu sản phẩm.
Sử dụng google-genai SDK (v2+).
"""
import json
from google import genai

from src.core.config import settings
from src.core.logging import logger


def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def _parse_json_response(text: str) -> list | dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def enhance_products(products: list[dict], site: str, category: str) -> list[dict]:
    """Dùng Gemini để chuẩn hóa brand, unit và gán category_tag."""
    if not products:
        return products

    sample = products[:10]
    prompt = f"""
Bạn là chuyên gia phân tích dữ liệu TMĐT Việt Nam.
Danh sách sản phẩm từ {site}, danh mục {category}:

{json.dumps(sample, ensure_ascii=False, indent=2)}

Hãy làm giàu dữ liệu — giữ nguyên tất cả trường, chỉ bổ sung/sửa:
1. "brand": suy ra từ tên nếu có thể
2. "unit": chuẩn hóa (hộp/chai/lon/thùng/gói/kg/lít...)
3. "category_tag": phân loại chi tiết (sữa tươi/sữa bột/bia chai/bia lon/...)

Trả về JSON array đúng số phần tử, không giải thích thêm.
"""
    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        enhanced: list = _parse_json_response(response.text)
        for i, original in enumerate(products):
            if i < len(enhanced):
                original.update({
                    k: enhanced[i][k]
                    for k in ("brand", "unit", "category_tag")
                    if enhanced[i].get(k)
                })
        return products
    except Exception as exc:
        logger.warning("AI enhance failed for %s/%s: %s", site, category, exc)
        return products


def analyze_site(html: str, url: str) -> dict:
    """Dùng Gemini để phân tích cấu trúc website và đề xuất chiến lược."""
    prompt = f"""
Phân tích đoạn HTML từ URL: {url}

HTML (tối đa 5000 ký tự):
{html[:5000]}

Đánh giá và trả về JSON:
{{
  "page_type": "product_list | product_detail | homepage | other",
  "selectors": {{"name": "...", "price": "...", "image": "...", "link": "..."}},
  "security_level": "low | medium | high",
  "strategy": "automated | directed",
  "notes": "nhận xét ngắn gọn"
}}

Chỉ trả về JSON thuần túy, không giải thích.
"""
    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        return _parse_json_response(response.text)
    except Exception as exc:
        logger.warning("Site analysis failed for %s: %s", url, exc)
        return {
            "page_type": "unknown",
            "selectors": {},
            "security_level": "medium",
            "strategy": "automated",
            "notes": f"Lỗi phân tích: {exc}",
        }
