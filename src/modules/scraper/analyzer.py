"""Phase 1 — Gemini-powered HTML structure analyzer.

Supports both google-genai (new SDK) and google-generativeai (old SDK).
"""
from __future__ import annotations

import json
import os
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

import requests

from shared.config import settings

_API_KEY: str = settings.GEMINI_API_KEY
_MODEL: str = settings.GEMINI_MODEL or "gemini-1.5-flash"

try:
    from google import genai as _genai_new  # type: ignore
except ImportError:
    _genai_new = None  # type: ignore

_genai_old = None
if _genai_new is None:
    try:
        import google.generativeai as _genai_old  # type: ignore
    except ImportError:
        _genai_old = None  # type: ignore


# ── Prompt ───────────────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
You are an expert web scraping engineer specialising in Vietnamese e-commerce sites \
for beverages, alcohol, tobacco, and dairy products.

Analyse the HTML below (from "{source_name}") and return ONLY a single valid JSON object \
(no markdown fences, no comments) with this schema:

{{
  "source_file": "{source_name}",
  "page_type": "homepage | product_list | product_detail | store_list | store_detail",
  "crawl_targets": [
    {{
      "entity": "products",
      "description": "All product cards on this page",
      "container_selector": "outermost wrapper CSS selector",
      "item_selector": "single-item CSS selector (relative to container)",
      "pagination": {{
        "type": "numbered | next_button | infinite_scroll | load_more | url_param | null",
        "next_button_selector": "CSS selector for next-page button, or null",
        "page_param": "URL query-param name, e.g. page",
        "total_pages_selector": "CSS selector showing total page count, or null",
        "url_pattern": "URL pattern with {{{{n}}}} placeholder, or null"
      }},
      "fields": [
        {{"name": "product_name",  "selector": "...", "attr": null,  "required": true,  "transform": "text_content"}},
        {{"name": "brand",         "selector": "...", "attr": null,  "required": false, "transform": "text_content"}},
        {{"name": "category",      "selector": "...", "attr": null,  "required": false, "transform": "text_content"}},
        {{"name": "alcohol_percent","selector": "...", "attr": null,  "required": false, "transform": "extract_percentage"}},
        {{"name": "volume_ml",     "selector": "...", "attr": null,  "required": false, "transform": "extract_volume_ml"}},
        {{"name": "price",         "selector": "...", "attr": null,  "required": true,  "transform": "clean_price"}},
        {{"name": "old_price",     "selector": "...", "attr": null,  "required": false, "transform": "clean_price"}},
        {{"name": "stock_status",  "selector": "...", "attr": null,  "required": false, "transform": "check_for_sold_out_indicator"}},
        {{"name": "rating",        "selector": "...", "attr": null,  "required": false, "transform": "extract_rating_from_html_attributes_or_classes"}},
        {{"name": "review_count",  "selector": "...", "attr": null,  "required": false, "transform": "extract_review_count_from_html_attributes_or_classes"}},
        {{"name": "image_url",     "selector": "img", "attr": "src", "required": false, "transform": null}},
        {{"name": "product_url",   "selector": "a",   "attr": "href","required": true,  "transform": null}}
      ]
    }},
    {{
      "entity": "branches",
      "description": "Store branches / chi nhánh",
      "container_selector": "",
      "item_selector": "",
      "pagination": null,
      "fields": [
        {{"name": "branch_name", "selector": "...", "attr": null,   "required": true,  "transform": "text_content"}},
        {{"name": "branch_url",  "selector": "a",   "attr": "href", "required": false, "transform": null}},
        {{"name": "address",     "selector": "...", "attr": null,   "required": true,  "transform": "text_content"}},
        {{"name": "phone",       "selector": "...", "attr": null,   "required": false, "transform": "text_content"}},
        {{"name": "email",       "selector": "...", "attr": null,   "required": false, "transform": "text_content"}}
      ]
    }},
    {{
      "entity": "company_profile",
      "description": "Company / brand info block",
      "container_selector": "",
      "item_selector": null,
      "pagination": null,
      "fields": [
        {{"name": "company_name",    "selector": "...", "attr": null,   "required": false, "transform": "text_content"}},
        {{"name": "company_address", "selector": "...", "attr": null,   "required": false, "transform": "text_content"}},
        {{"name": "company_phone",   "selector": "...", "attr": null,   "required": false, "transform": "text_content"}},
        {{"name": "company_email",   "selector": "...", "attr": null,   "required": false, "transform": "text_content"}},
        {{"name": "company_logo",    "selector": "img", "attr": "src", "required": false, "transform": null}}
      ]
    }}
  ],
  "notes": "Any special observations about this site"
}}

Rules:
- Use real CSS selectors found in the HTML, not generic placeholders.
- If a section is absent, set container_selector="" and item_selector="".
- For lazy-loaded images, use the correct attribute (data-lazy, data-src, data-original).
- Set pagination.type to null when no pagination is detected.
- Always include all three entities in crawl_targets.
- Return ONLY valid JSON — no extra text.

HTML:
{html_content}
"""


_USE_MOCK_MODE: bool = settings.USE_MOCK_MODE
_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
_PROMPT_VERSION: str = os.getenv("GEMINI_PROMPT_VERSION", "2026-04-27.1")
_CACHE_TTL_DAYS: int = int(os.getenv("GEMINI_CACHE_TTL_DAYS", "30"))

_ROOT_DIR = Path(__file__).resolve().parents[3]
_CACHE_DIR = Path(os.getenv("GEMINI_CACHE_DIR", str(_ROOT_DIR / "outputs" / "gemini_cache")))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Gemini helpers ────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    if _USE_MOCK_MODE:
        print("  ⚠️  Đang chạy ở chế độ MOCK (không gọi API thực)")
        return json.dumps({
            "source_file": "mock_test",
            "page_type": "product_list",
            "crawl_targets": [
                {
                    "entity": "products",
                    "description": "Mock products",
                    "container_selector": ".product-items",
                    "item_selector": ".item",
                    "pagination": {"type": "numbered", "next_button_selector": ".next"},
                    "fields": [
                        {"name": "product_name", "selector": "h3", "attr": None, "required": True, "transform": "text_content"},
                        {"name": "price", "selector": ".price", "attr": None, "required": True, "transform": "clean_price"},
                        {"name": "product_url", "selector": "a", "attr": "href", "required": True, "transform": None}
                    ]
                },
                {"entity": "branches", "description": "", "container_selector": "", "item_selector": "", "pagination": None, "fields": []},
                {"entity": "company_profile", "description": "", "container_selector": "", "item_selector": None, "pagination": None, "fields": []}
            ]
        })

    if not _API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )
    if _genai_new is not None:
        client = _genai_new.Client(api_key=_API_KEY)
        response = client.models.generate_content(model=_MODEL, contents=prompt)
        return response.text
    if _genai_old is not None:
        _genai_old.configure(api_key=_API_KEY)
        model = _genai_old.GenerativeModel(_MODEL)
        response = model.generate_content(prompt)
        return response.text
    raise ImportError(
        "No Gemini SDK found. Run: pip install google-genai  OR  pip install google-generativeai"
    )


def _cache_key(*, source: str, html_preview: str) -> str:
    h = hashlib.sha256()
    h.update(_PROMPT_VERSION.encode("utf-8"))
    h.update(b"\0")
    h.update(source.encode("utf-8"))
    h.update(b"\0")
    h.update(html_preview.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def _read_cache(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None

    try:
        st = path.stat()
        if _CACHE_TTL_DAYS > 0:
            if datetime.now() - datetime.fromtimestamp(st.st_mtime) > timedelta(days=_CACHE_TTL_DAYS):
                return None

        raw = path.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_cache(key: str, data: dict) -> None:
    path = _cache_path(key)
    payload = {"_meta": {"prompt_version": _PROMPT_VERSION}, **data}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_structure(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "not a dict"
    if "page_type" not in data or not isinstance(data.get("page_type"), str):
        return False, "missing page_type"
    if "crawl_targets" not in data or not isinstance(data.get("crawl_targets"), list):
        return False, "missing crawl_targets"

    # Require 3 entities present (as per prompt contract)
    entities = {t.get("entity") for t in data.get("crawl_targets", []) if isinstance(t, dict)}
    required = {"products", "branches", "company_profile"}
    missing = required - entities
    if missing:
        return False, f"missing entities: {sorted(missing)}"

    return True, "ok"


def _clean_json(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```", 1)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def _fetch_html(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_page_structure(
    *,
    url: Optional[str] = None,
    html_file: Optional[Union[str, Path]] = None,
    html_content: Optional[str] = None,
    source_name: str = "",
    html_limit: int = 20_000,
) -> dict:
    """Analyze a web page and return a crawl_targets structure dict.

    Provide exactly one of: *url*, *html_file*, or *html_content*.
    """
    provided = sum(x is not None for x in [url, html_file, html_content])
    if provided != 1:
        raise ValueError("Provide exactly one of: url, html_file, html_content")

    if url is not None:
        from urllib.parse import urlparse
        derived_name = source_name or urlparse(url).netloc
        print(f"  Fetching HTML from {url} …")
        raw_html = _fetch_html(url)
    elif html_file is not None:
        html_file = Path(html_file)
        derived_name = source_name or html_file.stem
        raw_html = html_file.read_text(encoding="utf-8", errors="ignore")
    else:
        derived_name = source_name or "unknown"
        raw_html = html_content  # type: ignore[assignment]

    preview = raw_html[:html_limit]
    cache_key = _cache_key(source=derived_name, html_preview=preview[:2000])
    cached = _read_cache(cache_key)
    if cached:
        ok, _ = _validate_structure(cached)
        if ok:
            print("  ✅ Cache hit")
            return cached

    prompt = _PROMPT_TEMPLATE.format(
        source_name=derived_name,
        html_content=preview,
    )

    attempt = 0
    last_err = ""
    while attempt <= _MAX_RETRIES:
        attempt += 1
        print(f"  Calling Gemini ({_MODEL}) for structure analysis … (attempt {attempt}/{_MAX_RETRIES + 1})")
        t0 = time.perf_counter()
        raw_response = _call_gemini(prompt)
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"  ⏱️  Gemini latency: {elapsed}s | chars={len(raw_response or '')}")

        json_text = _clean_json(raw_response)
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            last_err = f"invalid json: {exc}"
            continue

        if not isinstance(data, dict):
            last_err = "json is not an object"
            continue

        ok, msg = _validate_structure(data)
        if not ok:
            last_err = msg
            continue

        try:
            _write_cache(cache_key, data)
        except Exception:
            pass
        return data

    print(f"  ⚠️  Gemini returned invalid/insufficient JSON after retries: {last_err}")
    print(f"  Raw response (first 500 chars): {raw_response[:500]}")
    return {}
