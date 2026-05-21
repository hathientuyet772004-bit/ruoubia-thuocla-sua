"""
StructureGenerator — dùng Gemini Flash để generate CSS selectors cho domain.

Chiến lược tối ưu LLM calls:
  - Chỉ gọi 1 lần/domain để generate structure
  - Cache kết quả vào DB + file JSON
  - Fallback: per-page LLM extraction nếu selector không work
"""
from __future__ import annotations

import json
import os
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import google.generativeai as genai
from shared.config import settings

logger = logging.getLogger("smart_crawler.structure_generator")

# Cache directory để lưu structures
_CACHE_DIR = Path(__file__).parent / "cache" / "structures"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── Prompts ───────────────────────────────────────────────────────────────────

_STRUCTURE_PROMPT = """\
You are an expert web scraping engineer for Vietnamese e-commerce sites selling beverages, alcohol, tobacco, and dairy products.

Analyze the HTML below (from "{domain}") and return ONLY a single valid JSON object (no markdown fences) with this exact schema:

{{
  "domain": "{domain}",
  "page_type": "homepage | product_list | product_detail",
  "listing_urls": ["list of discovered product listing/category URLs"],
  "listing": {{
    "container_selector": "outermost CSS selector wrapping all product items",
    "item_selector": "single product card CSS selector",
    "pagination": {{
      "type": "numbered | next_button | url_param | load_more | infinite_scroll | null",
      "next_button_selector": "CSS selector for next-page button or null",
      "page_param": "URL param name for page number e.g. 'page' or null",
      "url_pattern": "URL with {{n}} placeholder e.g. '/products?page={{n}}' or null",
      "max_pages": null
    }},
    "fields": [
      {{"name": "product_name",   "selector": "css_selector", "attr": null,   "required": true,  "transform": "text_content"}},
      {{"name": "brand",          "selector": "css_selector", "attr": null,   "required": false, "transform": "text_content"}},
      {{"name": "category",       "selector": "css_selector", "attr": null,   "required": false, "transform": "text_content"}},
      {{"name": "price",          "selector": "css_selector", "attr": null,   "required": true,  "transform": "clean_price"}},
      {{"name": "old_price",      "selector": "css_selector", "attr": null,   "required": false, "transform": "clean_price"}},
      {{"name": "stock_status",   "selector": "css_selector", "attr": null,   "required": false, "transform": "check_for_sold_out_indicator"}},
      {{"name": "rating",         "selector": "css_selector", "attr": null,   "required": false, "transform": "extract_rating_from_html_attributes_or_classes"}},
      {{"name": "review_count",   "selector": "css_selector", "attr": null,   "required": false, "transform": "extract_review_count_from_html_attributes_or_classes"}},
      {{"name": "image_url",      "selector": "img",          "attr": "src",  "required": false, "transform": null}},
      {{"name": "product_url",    "selector": "a",            "attr": "href", "required": true,  "transform": null}}
    ]
  }},
  "product_detail": {{
    "fields": [
      {{"name": "product_name",   "selector": "css_selector", "attr": null, "required": true,  "transform": "text_content"}},
      {{"name": "brand",          "selector": "css_selector", "attr": null, "required": false, "transform": "text_content"}},
      {{"name": "category",       "selector": "css_selector", "attr": null, "required": false, "transform": "text_content"}},
      {{"name": "alcohol_percent","selector": "css_selector", "attr": null, "required": false, "transform": "extract_percentage"}},
      {{"name": "volume_ml",      "selector": "css_selector", "attr": null, "required": false, "transform": "extract_volume_ml"}},
      {{"name": "price",          "selector": "css_selector", "attr": null, "required": true,  "transform": "clean_price"}},
      {{"name": "old_price",      "selector": "css_selector", "attr": null, "required": false, "transform": "clean_price"}},
      {{"name": "stock_status",   "selector": "css_selector", "attr": null, "required": false, "transform": "check_for_sold_out_indicator"}},
      {{"name": "image_url",      "selector": "img",          "attr": "src","required": false,  "transform": null}}
    ]
  }},
  "notes": "Any observations about the site structure"
}}

RULES:
- Use REAL CSS selectors found in this HTML — no generic placeholders.
- For lazy images: check data-src, data-lazy, data-original attributes.
- Set pagination.type = null if no pagination found.
- listing_urls: list up to 5 category/listing page URLs found in nav/menu.
- Return ONLY valid JSON — no extra text, no markdown.

HTML (from {domain}):
{html_content}
"""

_FALLBACK_EXTRACT_PROMPT = """\
Extract product information from this HTML snippet.
Return ONLY a valid JSON object:

{{
  "product_name": "...",
  "brand": "...",
  "category": "...",
  "alcohol_percent": "...",
  "volume_ml": "...",
  "price": "...",
  "old_price": "...",
  "stock_status": "còn hàng | hết hàng",
  "rating": "...",
  "review_count": "...",
  "image_url": "...",
  "product_url": "..."
}}

If a field is missing, use empty string "".
Return ONLY JSON, no extra text.

HTML:
{html_snippet}
"""


# ── Mock responses ────────────────────────────────────────────────────────────

_MOCK_STRUCTURE = {
    "domain": "mock-domain.vn",
    "page_type": "product_list",
    "listing_urls": ["/ruou", "/bia", "/thuoc-la"],
    "listing": {
        "container_selector": ".product-items",
        "item_selector": ".product-item",
        "pagination": {
            "type": "url_param",
            "next_button_selector": None,
            "page_param": "page",
            "url_pattern": None,
            "max_pages": None,
        },
        "fields": [
            {"name": "product_name",  "selector": "h3.product-name", "attr": None,   "required": True,  "transform": "text_content"},
            {"name": "brand",         "selector": ".brand",           "attr": None,   "required": False, "transform": "text_content"},
            {"name": "price",         "selector": ".price",           "attr": None,   "required": True,  "transform": "clean_price"},
            {"name": "old_price",     "selector": ".old-price",       "attr": None,   "required": False, "transform": "clean_price"},
            {"name": "image_url",     "selector": "img",              "attr": "src",  "required": False, "transform": None},
            {"name": "product_url",   "selector": "a.product-link",   "attr": "href", "required": True,  "transform": None},
        ],
    },
    "product_detail": {
        "fields": [
            {"name": "product_name",    "selector": "h1.product-title",  "attr": None, "required": True,  "transform": "text_content"},
            {"name": "price",           "selector": ".product-price",     "attr": None, "required": True,  "transform": "clean_price"},
            {"name": "alcohol_percent", "selector": ".spec-alcohol",      "attr": None, "required": False, "transform": "extract_percentage"},
            {"name": "volume_ml",       "selector": ".spec-volume",       "attr": None, "required": False, "transform": "extract_volume_ml"},
            {"name": "image_url",       "selector": "img.product-img",    "attr": "src","required": False, "transform": None},
        ],
    },
    "notes": "Mock structure — chạy USE_MOCK_MODE=true",
}

_MOCK_PRODUCT = {
    "product_name": "Rượu Vang Mock 750ml",
    "brand": "Mock Brand",
    "category": "Rượu Vang",
    "alcohol_percent": "13.5%",
    "volume_ml": "750ml",
    "price": "250000",
    "old_price": "300000",
    "stock_status": "còn hàng",
    "rating": "4.5",
    "review_count": "120",
    "image_url": "https://example.com/wine.jpg",
    "product_url": "https://example.com/ruou-vang-mock",
}


# ── Gemini client ─────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    if settings.USE_MOCK_MODE:
        logger.warning("⚠️  MOCK MODE — không gọi Gemini API thực")
        return ""  # Caller sẽ handle

    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY chưa được set trong .env")

    try:
        from google import genai as _genai
        client = _genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
        return response.text
    except ImportError:
        pass

    try:
        import google.generativeai as _old
        _old.configure(api_key=settings.GEMINI_API_KEY)
        model = _old.GenerativeModel(settings.GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except ImportError:
        raise ImportError("Cài đặt: pip install google-genai")


def _clean_json(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```", 1)[1]
        if text.lower().startswith("json"):
            text = text[4:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(domain: str) -> Path:
    safe = domain.replace("/", "_").replace(":", "_")
    return _CACHE_DIR / f"{safe}.json"


def _load_cache(domain: str) -> Optional[dict]:
    p = _cache_path(domain)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            logger.info(f"[{domain}] ✅ Structure loaded from cache: {p.name}")
            return data
        except Exception:
            pass
    return None


def _save_cache(domain: str, structure: dict) -> None:
    p = _cache_path(domain)
    p.write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[{domain}] 💾 Structure cached: {p.name}")


# ── Public API ────────────────────────────────────────────────────────────────

class StructureGenerator:
    """
    Dùng Gemini Flash để generate CSS selectors cho một domain.

    - Gọi Gemini CHỈ 1 lần/domain (cache file + DB)
    - Hỗ trợ mock mode khi không có API key
    - Fallback per-page extraction nếu selectors fail
    """

    def __init__(self, html_limit: int = 25_000):
        self.html_limit = html_limit
        self._llm_calls = 0

    def generate_structure(
        self,
        domain: str,
        html_content: str,
        force_refresh: bool = False,
        feedback: str = None,
    ) -> dict:
        """
        Generate (hoặc load từ cache) structure cho domain.
        """
        if not force_refresh and not feedback:
            cached = _load_cache(domain)
            if cached:
                return cached

        if settings.USE_MOCK_MODE:
            structure = dict(_MOCK_STRUCTURE)
            structure["domain"] = domain
            _save_cache(domain, structure)
            return structure

        prompt = _STRUCTURE_PROMPT.format(
            domain=domain,
            html_content=html_content[: self.html_limit],
        )

        if feedback:
            prompt += f"\n\nCRITICAL FEEDBACK FROM PREVIOUS ATTEMPT: {feedback}\nPlease fix the selectors to ensure name and price are extracted correctly."

        logger.info(f"[{domain}] 🧠 Gọi Gemini để generate structure... (Feedback: {feedback})")
        raw = _call_gemini(prompt)
        self._llm_calls += 1

        try:
            structure = json.loads(_clean_json(raw))
            structure["_llm_model"] = settings.GEMINI_MODEL
            structure["_llm_call_count"] = self._llm_calls
            _save_cache(domain, structure)
            logger.info(f"[{domain}] ✅ Structure generated và cached")
            return structure
        except json.JSONDecodeError as e:
            logger.error(f"[{domain}] ❌ Gemini trả về JSON không hợp lệ: {e}")
            logger.debug(f"Raw response: {raw[:400]}")
            return {}

    def extract_product_fallback(self, html_snippet: str) -> dict:
        """
        Fallback: dùng LLM để extract 1 product từ HTML snippet.
        Chỉ gọi khi CSS selectors không extract được data.
        """
        if settings.USE_MOCK_MODE:
            return dict(_MOCK_PRODUCT)

        prompt = _FALLBACK_EXTRACT_PROMPT.format(
            html_snippet=html_snippet[:8_000]
        )

        logger.info(f"  ⚠️  Fallback LLM extraction triggered")
        raw = _call_gemini(prompt)
        self._llm_calls += 1

        try:
            return json.loads(_clean_json(raw))
        except json.JSONDecodeError:
            return {}

    @property
    def llm_calls(self) -> int:
        return self._llm_calls
