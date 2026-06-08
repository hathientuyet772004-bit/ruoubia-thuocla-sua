from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from apps.admin_center.backend.settings import settings

GEMINI_ALLOWED_TRANSFORMS = {
    "text_content",
    "clean_price",
    "extract_percentage",
    "extract_volume_ml",
    "check_for_sold_out_indicator",
    "extract_rating_from_html_attributes_or_classes",
    "extract_review_count_from_html_attributes_or_classes",
}


def _safe_html_excerpt(html: str, limit: int = 32000) -> str:
    """Keep metadata, page content, and footer evidence within the model budget."""
    soup = BeautifulSoup(html, "lxml")
    evidence: list[str] = []
    for node in soup.select(
        "script[type='application/ld+json'], meta[name], meta[property], link[rel='canonical'], "
        "address, [itemprop='brand'], [itemprop='address'], [itemprop='telephone'], "
        "a[href^='tel:'], footer"
    ):
        value = " ".join(str(node).split())
        if value:
            evidence.append(value[:4000])
    compact = " ".join(html.split())
    evidence_text = "\n".join(dict.fromkeys(evidence))
    remaining = max(4000, limit - len(evidence_text))
    head_size = remaining * 2 // 3
    tail_size = remaining - head_size
    return (
        "[STRUCTURED_EVIDENCE]\n"
        f"{evidence_text[: limit // 2]}\n"
        "[HTML_START]\n"
        f"{compact[:head_size]}\n"
        "[HTML_END]\n"
        f"{compact[-tail_size:]}"
    )[:limit]


def _normalize_model_name(model: str) -> str:
    value = model.strip()
    if "/models/" in value:
        value = value.split("/models/", 1)[1]
    if value.startswith("models/"):
        value = value.split("models/", 1)[1]
    return value


def _target_schema(target: str) -> dict[str, Any]:
    if target == "listing":
        return {
            "container_selector": "",
            "item_selector": "",
            "pagination": {
                "type": "none",
                "next_button_selector": None,
                "page_param": None,
                "url_pattern": None,
                "max_pages": None,
            },
            "fields": [],
        }
    if target == "stores":
        return {
            "container_selector": "",
            "item_selector": "",
            "fields": [],
        }
    return {"fields": []}


def _record_schema() -> dict[str, Any]:
    return {
        "entity_type": "product",
        "name": "sample name",
        "url": "https://example.com/product",
        "price": 0,
        "old_price": 0,
        "currency": "VND",
        "category": "sample category",
        "brand": "sample brand",
        "store_name": "sample store",
        "store_url": "https://example.com",
        "address": "sample address",
        "phone": "sample phone",
        "image_url": "https://example.com/image.jpg",
        "confidence": 0.5,
        "reason": "short reason",
    }


def build_gemini_prompt(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None) -> str:
    excerpt = _safe_html_excerpt(html)
    payload = {
        "domain": domain,
        "url": url,
        "page_type": page_type,
        "target_hint": target_hint or "auto",
        "known_targets": ["listing", "product_detail", "stores"],
        "notes": [
            "Return JSON only. No markdown. No code fences.",
            "Do not invent selectors that are not supported by the HTML.",
            "Every selector must match the supplied HTML excerpt.",
            "Prefer stable selectors with tag, class, id, attribute, or semantic structure.",
            "If the page supports multiple targets, include each target you can justify from the HTML.",
            "If a target cannot be justified, leave its object empty instead of hallucinating selectors.",
            "Inspect JSON-LD, itemprop, OpenGraph/meta tags, labeled specification rows, header, contact blocks, and footer.",
            "Do not use broad selectors such as img, a, [class*='brand'], or [class*='price'] unless scoped under a product item or product detail container.",
            "Use the same output shape as the Admin Center rule files.",
        ],
        "allowed_transforms": sorted(GEMINI_ALLOWED_TRANSFORMS),
        "output_shape": {
            "domain": domain,
            "page_type": page_type or "unknown",
            "listing": _target_schema("listing"),
            "product_detail": _target_schema("product_detail"),
            "stores": _target_schema("stores"),
            "notes": "short notes only",
        },
        "html_excerpt": excerpt,
    }
    return (
        "You are an extraction engineer. Read the HTML excerpt and produce a deterministic rule draft for the site.\n"
        "The result must be a single JSON object matching this schema:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "Rules:\n"
        "- Use only evidence in the HTML excerpt.\n"
        "- For listing pages, return selectors for container, item, pagination, and fields.\n"
        "- For product detail pages, return product_detail fields.\n"
        "- For store or branch pages, return stores selectors and fields.\n"
        "- Product fields must use these canonical names when evidenced: product_name, brand, category, price, old_price, image_url, product_url.\n"
        "- Store fields must use these canonical names when evidenced: store_name, store_address, store_phone, store_url. Never emit store_id.\n"
        "- For brand, check schema.org Product.brand, itemprop='brand', product metadata, and a labeled 'Thương hiệu'/'Brand' specification before using a visual class.\n"
        "- For store fields, inspect Organization/LocalBusiness JSON-LD, header, contact section, tel links, canonical URL, and footer.\n"
        "- On listing targets, product_name, price, and product_url are required. On product_detail, product_name and price are required; include product_url when a canonical link is available.\n"
        "- Store fields are site-level data and may be placed in stores even when the page is a product page.\n"
        "- Each field object must use: name, selector, attr, required, transform.\n"
        "- attr must be content for meta tags, href for links, src/data-src for images, or null for text.\n"
        "- Keep selectors concise and stable.\n"
        "- If a field is not evidenced, omit it and list it in notes. Never guess a selector from common e-commerce conventions.\n"
        "- Output JSON only."
    )


def build_ai_review_prompt(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None, max_items: int = 24) -> str:
    excerpt = _safe_html_excerpt(html)
    payload = {
        "domain": domain,
        "url": url,
        "page_type": page_type,
        "target_hint": target_hint or "auto",
        "max_items": max(1, min(int(max_items or 24), 50)),
        "notes": [
            "Return JSON only. No markdown. No code fences.",
            "Produce a review list, not extraction rules.",
            "Use only evidence in the HTML excerpt.",
            "If the page is dynamic or blocked, infer only what is visible in text/metadata.",
            "Mark every candidate with review_status='needs_review'.",
            "Prefer products and stores that an operator can verify manually.",
        ],
        "output_shape": {
            "domain": domain,
            "page_type": page_type or "unknown",
            "source_url": url,
            "items": [
                {
                    "entity_type": "product",
                    "name": "sample name",
                    "url": "https://example.com/product",
                    "price": 0,
                    "currency": "VND",
                    "store_name": "sample store",
                    "store_url": "https://example.com",
                    "address": "sample address",
                    "phone": "sample phone",
                    "image_url": "https://example.com/image.jpg",
                    "confidence": 0.5,
                    "reason": "short reason",
                    "review_status": "needs_review",
                }
            ],
            "notes": "short notes only",
        },
        "html_excerpt": excerpt,
    }
    return (
        "You are an AI data collection agent for a review queue.\n"
        "Extract a candidate list from the HTML excerpt for human review.\n"
        "The result must be a single JSON object matching this schema:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "Rules:\n"
        "- Use only evidence visible in the excerpt.\n"
        "- Produce candidate rows for products, stores, or both if justified.\n"
        "- Each item must include entity_type, name, url, price, currency, store_name, store_url, address, phone, image_url, confidence, reason, review_status.\n"
        "- review_status must be 'needs_review' for every item.\n"
        "- Keep confidence between 0 and 1.\n"
        "- If the page is a category/listing page, return multiple products.\n"
        "- If the page is a store/contact page, return store candidates.\n"
        "- Output JSON only."
    )


def build_record_extraction_prompt(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None, max_items: int = 24) -> str:
    excerpt = _safe_html_excerpt(html)
    payload = {
        "domain": domain,
        "url": url,
        "page_type": page_type,
        "target_hint": target_hint or "auto",
        "max_items": max(1, min(int(max_items or 24), 50)),
        "notes": [
            "Return JSON only. No markdown. No code fences.",
            "Return only concrete products or stores that are directly evidenced by the HTML excerpt.",
            "Do not return section titles, breadcrumbs, category headings, or generic labels as records.",
            "Prefer product rows with a product name, URL, and price when the page is a listing or product page.",
            "Prefer store rows with a store name, address, phone, or URL when the page is a store/contact page.",
            "If the page is ambiguous, return the smallest justified set of records instead of guessing.",
            "Use the same currency and price format as visible in the page when possible.",
        ],
        "output_shape": {
            "domain": domain,
            "page_type": page_type or "unknown",
            "source_url": url,
            "items": [_record_schema()],
            "notes": "short notes only",
        },
        "html_excerpt": excerpt,
    }
    return (
        "You are an AI extraction agent. Read the HTML excerpt and produce normalized records for the admin system.\n"
        "The result must be a single JSON object matching this schema:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "Rules:\n"
        "- Use only evidence visible in the excerpt.\n"
        "- entity_type must be 'product' or 'store'.\n"
        "- Keep names concrete and specific. Do not emit labels like 'Loại vang' unless that is a real product name in the page.\n"
        "- For products, include brand and price when visible. For stores, include address and phone when visible.\n"
        "- confidence must be between 0 and 1.\n"
        "- If a field is not visible, omit it or leave it empty.\n"
        "- Output JSON only."
    )


def build_synthetic_data_prompt(
    *,
    row_count: int,
    product_types: list[str],
    reference_sources: list[str],
    region: str,
    output_columns: list[str],
) -> str:
    payload = {
        "SO_LUONG": row_count,
        "DANH_SACH_LOAI_SAN_PHAM": product_types,
        "DANH_SACH_NGUON_THAM_KHAO": reference_sources,
        "KHU_VUC": region,
        "DINH_DANG_COT": output_columns,
        "output_shape": {
            "rows": [
                {column: f"sample {column}" for column in output_columns}
            ]
        },
    }
    return (
        "Bạn là chuyên gia thu thập, kiểm chứng và chuẩn hóa dữ liệu sản phẩm bán lẻ tại Việt Nam.\n\n"
        "Nhiệm vụ của bạn là tạo bảng dữ liệu sản phẩm theo cấu trúc tôi cung cấp, dựa trên số lượng, loại sản phẩm và nguồn tham khảo đầu vào.\n\n"
        "THÔNG TIN ĐẦU VÀO:\n"
        f"- Số lượng dòng cần tạo: {row_count}\n"
        f"- Danh sách loại sản phẩm: {', '.join(product_types)}\n"
        f"- Nguồn/website/sàn tham khảo: {', '.join(reference_sources)}\n"
        f"- Khu vực ưu tiên: {region}\n"
        f"- Cấu trúc cột đầu ra: {', '.join(output_columns)}\n\n"
        "MỤC TIÊU:\n"
        "Tạo dữ liệu gần với thực tế, có thể dùng cho Excel/CSV, phân tích dữ liệu, demo hệ thống hoặc huấn luyện mô hình.\n\n"
        "YÊU CẦU CHUNG:\n"
        "1. Chỉ tạo đúng số lượng dòng theo SO_LUONG.\n"
        "2. Chỉ tạo sản phẩm thuộc các loại trong DANH_SACH_LOAI_SAN_PHAM.\n"
        "3. Chỉ tham khảo hoặc mô phỏng theo các nguồn trong DANH_SACH_NGUON_THAM_KHAO.\n"
        "4. Dữ liệu phải giống dữ liệu sản phẩm thật trên thị trường Việt Nam.\n"
        "5. Tên sản phẩm phải có thương hiệu, dòng sản phẩm và quy cách nếu có.\n"
        "6. Không tạo tên chung chung như Sản phẩm A, Rượu loại 1, Sữa loại 2.\n"
        "7. Không tạo sản phẩm trùng lặp hoàn toàn.\n"
        "8. Giá phải hợp lý theo từng loại sản phẩm.\n"
        "9. Rating nằm trong khoảng 4.0 đến 5.0, làm tròn 1 chữ số thập phân.\n"
        "10. Tên cửa hàng/kênh bán phải thực tế, ví dụ Official Store, siêu thị, chuỗi bán lẻ hoặc cửa hàng online.\n"
        "11. Địa chỉ ghi theo khu vực được truyền vào hoặc các giá trị hợp lý như Hà Nội, TP.HCM, Đà Nẵng, Toàn quốc, Online.\n"
        "12. Nếu có cột nguồn tham khảo, chỉ ghi trang chủ, trang tìm kiếm hoặc nguồn chính thức; không bịa link sản phẩm chi tiết nếu không chắc chắn.\n"
        "13. Không thêm cột ngoài DINH_DANG_COT.\n\n"
        "QUY TẮC AN TOÀN THEO LOẠI SẢN PHẨM:\n"
        "- Nếu loại sản phẩm là rượu, bia, thuốc lá hoặc hàng giới hạn độ tuổi: chỉ tạo dữ liệu phục vụ học tập, phân tích hoặc quản lý danh mục; không viết nội dung quảng cáo; không khuyến khích sử dụng; không ghi khuyến mãi, ưu đãi, lời mời mua; không hướng dẫn nơi mua trực tiếp cho người dùng; không mô tả hương vị theo hướng hấp dẫn.\n"
        "- Nếu loại sản phẩm là sữa, thực phẩm, hàng tiêu dùng: có thể ghi thông tin sản phẩm, thương hiệu, dung tích, khối lượng, quy cách đóng gói; không đưa thông tin y tế hoặc công dụng vượt quá dữ liệu sản phẩm thông thường.\n\n"
        "QUY TẮC PHÂN BỔ:\n"
        "- Nếu có nhiều loại sản phẩm, hãy phân bổ tương đối đều giữa các loại.\n"
        "- Nếu số lượng không chia đều, phần dư phân bổ cho các loại đầu tiên trong danh sách.\n\n"
        "QUY TẮC GIÁ THAM KHẢO:\n"
        "- Với mỗi loại sản phẩm, hãy tự suy luận khoảng giá hợp lý theo thị trường Việt Nam.\n"
        "- Giá phải là số nguyên VND.\n"
        "- Không ghi ký hiệu đ, VNĐ trong ô giá nếu cột yêu cầu là số.\n"
        "- Không tạo giá quá phi thực tế.\n\n"
        "YÊU CẦU ĐỊNH DẠNG CHO API:\n"
        "- Trả về JSON duy nhất. Không markdown. Không code fence.\n"
        "- JSON phải khớp schema sau, rows có đúng các key trong DINH_DANG_COT và đúng thứ tự cột.\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _extract_json_text(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if "\n" in candidate:
            candidate = candidate.split("\n", 1)[1]
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        return candidate[start : end + 1]
    return candidate


def _normalize_section(section: Any) -> dict[str, Any]:
    if not isinstance(section, dict):
        return {}
    normalized = dict(section)
    if "pagination" in normalized and not isinstance(normalized["pagination"], dict):
        normalized["pagination"] = {}
    fields = normalized.get("fields")
    if isinstance(fields, list):
        normalized["fields"] = [
            {
                "name": str(field.get("name") or ""),
                "selector": str(field.get("selector") or ""),
                "attr": field.get("attr"),
                "required": bool(field.get("required", False)),
                "transform": field.get("transform")
                if isinstance(field.get("transform"), str) and field.get("transform") in GEMINI_ALLOWED_TRANSFORMS
                else None,
            }
            for field in fields
            if isinstance(field, dict) and field.get("name")
        ]
    return normalized


def parse_gemini_rule(raw_text: str) -> dict[str, Any]:
    payload = json.loads(_extract_json_text(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Gemini response must be a JSON object")
    output_shape = payload.get("output_shape") if isinstance(payload.get("output_shape"), dict) else {}
    listing = payload.get("listing") if isinstance(payload.get("listing"), dict) else output_shape.get("listing")
    product_detail = (
        payload.get("product_detail")
        if isinstance(payload.get("product_detail"), dict)
        else output_shape.get("product_detail")
    )
    stores = payload.get("stores") if isinstance(payload.get("stores"), dict) else output_shape.get("stores")
    result = {
        "domain": payload.get("domain"),
        "page_type": payload.get("page_type") or "unknown",
        "listing": _normalize_section(listing),
        "product_detail": _normalize_section(product_detail),
        "stores": _normalize_section(stores),
        "notes": payload.get("notes") or "",
    }
    return result


def parse_ai_review_candidates(raw_text: str) -> dict[str, Any]:
    payload = json.loads(_extract_json_text(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Gemini response must be a JSON object")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entity_type = str(item.get("entity_type") or "product").strip().lower()
        if entity_type not in {"product", "store"}:
            entity_type = "product"
        normalized_items.append({
            "entity_type": entity_type,
            "name": str(item.get("name") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "price": item.get("price"),
            "currency": str(item.get("currency") or "VND").strip() or "VND",
            "store_name": str(item.get("store_name") or "").strip(),
            "store_url": str(item.get("store_url") or "").strip(),
            "address": str(item.get("address") or "").strip(),
            "phone": str(item.get("phone") or "").strip(),
            "image_url": str(item.get("image_url") or "").strip(),
            "confidence": max(0.0, min(float(item.get("confidence") or 0.0), 1.0)),
            "reason": str(item.get("reason") or "").strip(),
            "review_status": str(item.get("review_status") or "needs_review").strip() or "needs_review",
        })
    return {
        "domain": payload.get("domain"),
        "page_type": payload.get("page_type") or "unknown",
        "source_url": payload.get("source_url"),
        "notes": payload.get("notes") or "",
        "items": normalized_items,
    }


def parse_gemini_records(raw_text: str) -> dict[str, Any]:
    payload = json.loads(_extract_json_text(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Gemini response must be a JSON object")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entity_type = str(item.get("entity_type") or "product").strip().lower()
        if entity_type not in {"product", "store"}:
            entity_type = "product"
        confidence = item.get("confidence")
        try:
            confidence_value = float(confidence) if confidence is not None else 0.5
        except (TypeError, ValueError):
            confidence_value = 0.5
        normalized_items.append({
            "entity_type": entity_type,
            "name": str(item.get("name") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "price": item.get("price"),
            "old_price": item.get("old_price"),
            "currency": str(item.get("currency") or "VND").strip() or "VND",
            "category": str(item.get("category") or "").strip(),
            "brand": str(item.get("brand") or "").strip(),
            "store_name": str(item.get("store_name") or "").strip(),
            "store_url": str(item.get("store_url") or "").strip(),
            "address": str(item.get("address") or "").strip(),
            "phone": str(item.get("phone") or "").strip(),
            "image_url": str(item.get("image_url") or "").strip(),
            "confidence": max(0.0, min(confidence_value, 1.0)),
            "reason": str(item.get("reason") or "").strip(),
        })
    return {
        "domain": payload.get("domain"),
        "page_type": payload.get("page_type") or "unknown",
        "source_url": payload.get("source_url"),
        "notes": payload.get("notes") or "",
        "items": normalized_items,
    }


def parse_synthetic_rows(raw_text: str, output_columns: list[str], row_count: int) -> list[dict[str, Any]]:
    payload = json.loads(_extract_json_text(raw_text))
    if not isinstance(payload, dict):
        raise ValueError("Gemini response must be a JSON object")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("Gemini response must include rows")
    normalized_rows = []
    for row in rows[:row_count]:
        if not isinstance(row, dict):
            continue
        normalized_rows.append({column: row.get(column, "") for column in output_columns})
    if len(normalized_rows) != row_count:
        raise ValueError(f"Gemini returned {len(normalized_rows)} rows, expected {row_count}")
    return normalized_rows


@dataclass
class GeminiExtractionResult:
    model: str
    prompt: str
    draft: dict[str, Any]
    validation: dict[str, Any]


@dataclass
class GeminiReviewResult:
    model: str
    prompt: str
    candidates: dict[str, Any]


@dataclass
class GeminiRecordsResult:
    model: str
    prompt: str
    records: dict[str, Any]


@dataclass
class GeminiSyntheticDataResult:
    model: str
    prompt: str
    rows: list[dict[str, Any]]


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        configured_model = model or getattr(settings, "GEMINI_MODEL", "") or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.model = _normalize_model_name(configured_model)

    def available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = json.dumps({
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc.code} {exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

        candidates = payload.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini API returned no candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text.strip():
            raise RuntimeError("Gemini API returned empty text")
        return text


def validate_draft(html: str | None, draft: dict[str, Any]) -> dict[str, Any]:
    from apps.admin_center.backend.services import field_preview

    validation: dict[str, Any] = {"targets": {}, "accepted": False}
    if not html:
        return validation

    total_targets = 0
    accepted_targets = 0
    accepted_product_targets = 0
    recommended_fields = {
        "listing": {"product_name", "price", "product_url", "brand"},
        "product_detail": {"product_name", "price", "product_url", "brand"},
        "stores": {"store_name", "store_url", "store_address", "store_phone"},
    }
    for target_name in ("listing", "product_detail", "stores"):
        section = draft.get(target_name) or {}
        fields = section.get("fields") if isinstance(section, dict) else []
        if not fields:
            continue
        total_targets += 1
        preview = field_preview(html, fields)
        required_fields = [row for row in preview if row.get("required")]
        passed_required = all((row.get("matches") or 0) > 0 for row in required_fields) if required_fields else False
        field_hits = sum(1 for row in preview if (row.get("matches") or 0) > 0)
        score = round(field_hits / len(preview), 2) if preview else 0.0
        field_names = {str(row.get("name") or "") for row in preview if (row.get("matches") or 0) > 0}
        missing_recommended = sorted(recommended_fields[target_name] - field_names)
        if passed_required:
            accepted_targets += 1
            if target_name in {"listing", "product_detail"}:
                accepted_product_targets += 1
        validation["targets"][target_name] = {
            "preview": preview,
            "required_pass": passed_required,
            "field_score": score,
            "missing_recommended": missing_recommended,
        }

    validation["accepted"] = bool(total_targets and accepted_product_targets)
    validation["accepted_targets"] = accepted_targets
    validation["accepted_product_targets"] = accepted_product_targets
    validation["warnings"] = [
        f"{target}: missing {', '.join(result['missing_recommended'])}"
        for target, result in validation["targets"].items()
        if result.get("missing_recommended")
    ]
    return validation


def analyze_html(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None) -> GeminiExtractionResult:
    client = GeminiClient()
    prompt = build_gemini_prompt(domain=domain, html=html, url=url, page_type=page_type, target_hint=target_hint)
    raw_text = client.generate(prompt)
    draft = parse_gemini_rule(raw_text)
    draft["domain"] = draft.get("domain") or domain
    validation = validate_draft(html, draft)
    validation["model"] = client.model
    validation["target_hint"] = target_hint or "auto"
    return GeminiExtractionResult(model=client.model, prompt=prompt, draft=draft, validation=validation)


def extract_records(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None, max_items: int = 24) -> GeminiRecordsResult:
    client = GeminiClient()
    prompt = build_record_extraction_prompt(domain=domain, html=html, url=url, page_type=page_type, target_hint=target_hint, max_items=max_items)
    raw_text = client.generate(prompt)
    records = parse_gemini_records(raw_text)
    records["domain"] = records.get("domain") or domain
    records["page_type"] = records.get("page_type") or (page_type or "unknown")
    return GeminiRecordsResult(model=client.model, prompt=prompt, records=records)


def generate_review_candidates(*, domain: str, html: str, url: str | None = None, page_type: str | None = None, target_hint: str | None = None, max_items: int = 24) -> GeminiReviewResult:
    client = GeminiClient()
    prompt = build_ai_review_prompt(domain=domain, html=html, url=url, page_type=page_type, target_hint=target_hint, max_items=max_items)
    raw_text = client.generate(prompt)
    candidates = parse_ai_review_candidates(raw_text)
    candidates["domain"] = candidates.get("domain") or domain
    candidates["page_type"] = candidates.get("page_type") or (page_type or "unknown")
    return GeminiReviewResult(model=client.model, prompt=prompt, candidates=candidates)


def generate_synthetic_data(
    *,
    row_count: int,
    product_types: list[str],
    reference_sources: list[str],
    region: str,
    output_columns: list[str],
) -> GeminiSyntheticDataResult:
    client = GeminiClient()
    prompt = build_synthetic_data_prompt(
        row_count=row_count,
        product_types=product_types,
        reference_sources=reference_sources,
        region=region,
        output_columns=output_columns,
    )
    raw_text = client.generate(prompt)
    rows = parse_synthetic_rows(raw_text, output_columns, row_count)
    return GeminiSyntheticDataResult(model=client.model, prompt=prompt, rows=rows)
