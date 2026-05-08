"""
Gemini AI Extractor — dùng Gemini để trích xuất và làm sạch dữ liệu sản phẩm.
"""
import os
import json
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_model():
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-1.5-flash")


def extract_products_from_html(html: str, site: str, category: str) -> list:
    """Dùng Gemini để phân tích HTML thô và trích xuất danh sách sản phẩm."""
    model = get_model()

    prompt = f"""
Bạn là chuyên gia phân tích dữ liệu TMĐT Việt Nam.
Phân tích đoạn HTML sau từ trang {site}, danh mục: {category}.
Trích xuất tất cả sản phẩm có thể tìm thấy.

HTML (tối đa 8000 ký tự):
{html[:8000]}

Trả về JSON array với format:
[
  {{
    "name": "tên sản phẩm",
    "brand": "thương hiệu (nếu có)",
    "price": 0,
    "unit": "đơn vị (hộp/chai/lon...)",
    "image_url": "",
    "product_url": "",
    "rating": 0,
    "sold_count": 0
  }}
]

Chỉ trả về JSON thuần túy, không giải thích thêm.
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        return []


def enhance_product_data(products: list, site: str, category: str) -> list:
    """Dùng Gemini để làm giàu và chuẩn hóa dữ liệu sản phẩm đã có."""
    if not products:
        return products

    model = get_model()
    sample = products[:10]

    prompt = f"""
Bạn là chuyên gia phân tích dữ liệu sản phẩm TMĐT Việt Nam.
Danh sách sản phẩm từ {site}, danh mục {category}:

{json.dumps(sample, ensure_ascii=False, indent=2)}

Hãy chuẩn hóa và làm giàu dữ liệu:
1. Xác định/điền thêm trường "brand" nếu có thể suy ra từ tên
2. Chuẩn hóa "unit" (hộp/chai/lon/thùng/gói...)
3. Xác định "category_tag" cho từng sản phẩm (ví dụ: sữa tươi, sữa bột, bia chai, bia lon...)

Giữ nguyên tất cả trường cũ, chỉ bổ sung/sửa brand, unit, category_tag.
Trả về JSON array, không giải thích.
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        enhanced = json.loads(text.strip())
        for i, p in enumerate(products):
            if i < len(enhanced):
                products[i].update(enhanced[i])
        return products
    except Exception:
        return products


def analyze_site_structure(html: str, url: str) -> dict:
    """Dùng Gemini để phân tích cấu trúc trang và đề xuất chiến lược thu thập."""
    model = get_model()

    prompt = f"""
Phân tích đoạn HTML từ URL: {url}

HTML:
{html[:5000]}

Hãy đánh giá:
1. Cấu trúc trang (danh sách sản phẩm / trang chi tiết / trang chủ...)
2. Selector CSS phù hợp để lấy: tên sp, giá, ảnh, link
3. Mức độ chống bot (thấp/trung bình/cao)
4. Chiến lược thu thập đề xuất (automated/directed)
5. Phân tích thêm

Trả về JSON:
{{
  "page_type": "...",
  "selectors": {{"name": "...", "price": "...", "image": "...", "link": "..."}},
  "security_level": "low|medium|high",
  "strategy": "automated|directed",
  "notes": "..."
}}
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        return {
            "page_type": "unknown",
            "selectors": {},
            "security_level": "medium",
            "strategy": "automated",
            "notes": str(e),
        }
