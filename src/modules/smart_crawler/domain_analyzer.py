"""
DomainAnalyzer — tự động phát hiện chiến lược crawl tối ưu cho mỗi domain.

Logic:
  1. HEAD / GET request → kiểm tra status code, redirect
  2. Kiểm tra JS-require (nội dung rỗng/ script tag heavy)
  3. Kiểm tra anti-bot signals (Cloudflare, captcha, 403/429)
  4. Kiểm tra API endpoint từ network patterns
  5. Kiểm tra sitemap / listing page

Output:
  {
    "can_crawl_direct": bool,
    "has_api": bool,
    "has_listing": bool,
    "anti_bot": bool,
    "js_required": bool,
    "strategy": "api" | "html" | "mhtml",
    "status_code": int,
    "redirect_url": str | None,
    "notes": str
  }
"""
from __future__ import annotations

import re
import time
import logging
from typing import Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("smart_crawler.domain_analyzer")

# ── Constants ─────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

_ANTI_BOT_PATTERNS = [
    r"cloudflare",
    r"cf-browser-verification",
    r"enable javascript",
    r"just a moment",
    r"ddos-guard",
    r"checking your browser",
    r"captcha",
    r"recaptcha",
    r"hcaptcha",
    r"bot detection",
    r"access denied",
    r"403 forbidden",
    r"rate limit",
    r"too many requests",
]

_API_URL_PATTERNS = [
    r"/api/v\d+/",
    r"/rest/v\d+/",
    r"\.json(\?|$)",
    r"/catalog/product",
    r"/products\.json",
    r"graphql",
]

_LISTING_URL_PATTERNS = [
    r"/collections/",
    r"/danh-muc/",
    r"/category/",
    r"/products/?$",
    r"/san-pham",
    r"/thuoc-la",
    r"/ruou",
    r"/sua",
    r"/do-uong",
]

# ── Async-friendly request helper ─────────────────────────────────────────────

def _safe_get(session: requests.Session, url: str, timeout: int = 15) -> requests.Response | None:
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        return resp
    except requests.exceptions.SSLError:
        try:
            return session.get(url, timeout=timeout, verify=False, allow_redirects=True)
        except Exception as e:
            logger.warning(f"SSL fallback failed for {url}: {e}")
            return None
    except Exception as e:
        logger.warning(f"Request failed for {url}: {e}")
        return None


# ── Detection helpers ─────────────────────────────────────────────────────────

def _detect_anti_bot(resp: requests.Response, html: str) -> bool:
    """Trả về True nếu phát hiện anti-bot."""
    if resp.status_code in (403, 429, 503):
        return True
    lower_html = html.lower()
    for pattern in _ANTI_BOT_PATTERNS:
        if re.search(pattern, lower_html, re.IGNORECASE):
            return True
    # Cloudflare ray-id header
    if "cf-ray" in resp.headers:
        return True
    return False


def _detect_js_required(html: str) -> bool:
    """Trả về True nếu trang cần JS để render content."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body
    if not body:
        return True

    # Lấy text thực (loại scripts/style)
    for tag in body.find_all(["script", "style", "noscript"]):
        tag.decompose()
    visible_text = body.get_text(strip=True)

    # Nếu quá ít text → JS-rendered
    if len(visible_text) < 200:
        return True

    # Kiểm tra Next.js / Nuxt / Vue / React mounting placeholders
    js_signals = [
        "id=\"__next\"",
        "id=\"app\"",
        "data-server-rendered",
        "window.__NUXT__",
        "window.__INITIAL_STATE__",
        "__REACT_APP",
    ]
    for sig in js_signals:
        if sig in html:
            return True

    return False


def _detect_has_api(base_url: str, html: str, session: requests.Session) -> bool:
    """Kiểm tra xem domain có API endpoint dễ crawl không."""
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Thử các endpoint API phổ biến của e-commerce
    api_candidates = [
        "/products.json",
        "/collections.json",
        "/api/v2/products",
        "/api/products",
    ]
    for path in api_candidates:
        url = origin + path
        try:
            r = session.get(url, timeout=8)
            if r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
                logger.info(f"  ✅ API found: {url}")
                return True
        except Exception:
            continue

    # Kiểm tra script tags cho API URL patterns
    for pattern in _API_URL_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            return True

    return False


def _detect_has_listing(base_url: str, html: str, session: requests.Session) -> bool:
    """Kiểm tra xem domain có trang listing sản phẩm không."""
    # Kiểm tra URL hiện tại
    for pattern in _LISTING_URL_PATTERNS:
        if re.search(pattern, base_url, re.IGNORECASE):
            return True

    # Kiểm tra links trong homepage
    soup = BeautifulSoup(html, "lxml")
    links = [a.get("href", "") for a in soup.select("a[href]")]

    count = 0
    for link in links:
        for pattern in _LISTING_URL_PATTERNS:
            if re.search(pattern, str(link), re.IGNORECASE):
                count += 1
                break
        if count >= 2:
            return True

    return False


def _check_sitemap(base_url: str, session: requests.Session) -> bool:
    """Kiểm tra sitemap.xml để xác nhận có listing pages."""
    parsed = urlparse(base_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    try:
        r = session.get(sitemap_url, timeout=8)
        if r.status_code == 200 and "</url>" in r.text:
            return True
    except Exception:
        pass
    return False


# ── Main Analyzer ─────────────────────────────────────────────────────────────

class DomainAnalyzer:
    """
    Phân tích domain để quyết định chiến lược crawl tối ưu.

    Usage:
        analyzer = DomainAnalyzer()
        result = analyzer.analyze("https://ruoutot.net/")
        # result["strategy"] → "html" | "api" | "mhtml"
    """

    def __init__(self, timeout: int = 15, delay: float = 1.0):
        self.timeout = timeout
        self.delay = delay
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def analyze(self, url: str) -> dict:
        """
        Phân tích URL và trả về domain intelligence dict.

        Returns:
            {
                "domain": str,
                "can_crawl_direct": bool,
                "has_api": bool,
                "has_listing": bool,
                "anti_bot": bool,
                "js_required": bool,
                "strategy": "api" | "html" | "mhtml",
                "status_code": int,
                "redirect_url": str | None,
                "notes": str
            }
        """
        domain = urlparse(url).netloc or url
        logger.info(f"[{domain}] 🔍 Bắt đầu phân tích...")

        result = {
            "domain": domain,
            "can_crawl_direct": False,
            "has_api": False,
            "has_listing": False,
            "anti_bot": False,
            "js_required": False,
            "strategy": "mhtml",
            "status_code": None,
            "redirect_url": None,
            "notes": "",
        }

        # ── Step 1: Fetch trang chủ ──────────────────────────────────────────
        resp = _safe_get(self._session, url, self.timeout)
        if resp is None:
            result["notes"] = "Cannot connect to domain"
            logger.warning(f"[{domain}] ❌ Không thể kết nối")
            return result

        result["status_code"] = resp.status_code
        if resp.url != url:
            result["redirect_url"] = resp.url

        html = resp.text or ""

        # ── Step 2: Anti-bot Detection ───────────────────────────────────────
        is_anti_bot = _detect_anti_bot(resp, html)
        result["anti_bot"] = is_anti_bot

        if is_anti_bot:
            logger.warning(f"[{domain}] 🚫 Anti-bot detected!")
            result["notes"] = "Anti-bot system detected. Use MHTML strategy."
            result["strategy"] = "mhtml"
            return result  # Sớm return — không cần check thêm

        # ── Step 3: JS-required Detection ───────────────────────────────────
        js_req = _detect_js_required(html)
        result["js_required"] = js_req

        if js_req:
            logger.info(f"[{domain}] ⚡ JS-required detected. Checking Playwright...")
            # Vẫn thử crawl nhưng cần Playwright
            result["notes"] = "Site requires JavaScript rendering."

        # ── Step 4: API Detection ────────────────────────────────────────────
        if delay := self.delay:
            time.sleep(delay)

        has_api = _detect_has_api(url, html, self._session)
        result["has_api"] = has_api

        # ── Step 5: Listing Detection ────────────────────────────────────────
        has_listing = _detect_has_listing(url, html, self._session)
        result["has_listing"] = has_listing

        # ── Step 6: Sitemap check ────────────────────────────────────────────
        if not has_listing:
            has_listing = _check_sitemap(url, self._session)
            result["has_listing"] = has_listing

        # ── Step 7: Strategy Decision ────────────────────────────────────────
        if resp.status_code == 200 and not is_anti_bot:
            result["can_crawl_direct"] = True

            if has_api:
                result["strategy"] = "api"
                result["notes"] += " | API endpoint available."
            elif js_req:
                result["strategy"] = "headless"
                result["notes"] += " | Requires Playwright rendering."
            else:
                result["strategy"] = "html"
                result["notes"] += " | Direct HTML crawl available."
        else:
            result["strategy"] = "mhtml"
            result["notes"] += " | Fallback to MHTML strategy."

        logger.info(
            f"[{domain}] ✅ Strategy: {result['strategy'].upper()} "
            f"| API: {has_api} | Anti-bot: {is_anti_bot} | JS: {js_req}"
        )
        return result

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
