"""
TemplateCrawler — crawl tự động theo structure dict được generate bởi LLM.

Hỗ trợ:
  - Crawl listing pages với pagination
  - Crawl product detail pages
  - Fallback sang LLM nếu selector không extract được data
  - Rate limiting + retry
"""
from __future__ import annotations

import time
import logging
import random
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

from .structure_generator import StructureGenerator

logger = logging.getLogger("smart_crawler.template_crawler")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_LAZY_ATTRS = ("data-lazy", "data-src", "data-original", "data-url", "data-original-src")

# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class CrawledProduct:
    product_name: str = ""
    brand: str = ""
    category: str = ""
    alcohol_percent: str = ""
    volume_ml: str = ""
    price: str = ""
    price_numeric: float = 0.0
    old_price: str = ""
    stock_status: str = ""
    rating: str = ""
    review_count: str = ""
    image_url: str = ""
    product_url: str = ""
    source_site: str = ""
    page_number: int = 1
    extraction_method: str = "selector"  # "selector" | "llm_fallback"
    confidence_score: float = 1.0  # 0.0 to 1.0
    validation_status: str = "valid"  # "valid" | "needs_review" | "invalid"

    def to_dict(self) -> dict:
        return asdict(self)


# ── Transform helpers ─────────────────────────────────────────────────────────

import re

def _clean_price(text: str) -> str:
    return re.sub(r"[^\d]", "", text)

def _price_to_float(text: str) -> float:
    nums = re.sub(r"[^\d]", "", text)
    return float(nums) if nums else 0.0

def _extract_percentage(text: str) -> str:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    return (m.group(1) + "%") if m else text.strip()

def _extract_volume_ml(text: str) -> str:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ml|cl|dl|l|lít|litre?s?)\b", text, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        if unit in ("l", "lít", "litre", "litres"):
            return str(int(val * 1000)) + "ml"
        if unit == "cl":
            return str(int(val * 10)) + "ml"
        return f"{val}ml"
    return text.strip()

_SOLD_OUT_PATTERNS = [r"hết\s*hàng", r"sold[- ]?out", r"out[- ]?of[- ]?stock", r"tạm\s*hết"]

def _check_sold_out(element: Tag, text: str) -> str:
    combined = (str(element) + " " + text).lower()
    for p in _SOLD_OUT_PATTERNS:
        if re.search(p, combined, re.IGNORECASE):
            return "Hết hàng"
    return "Còn hàng"

def _calculate_confidence(product: CrawledProduct) -> float:
    score = 1.0
    if not product.product_name: score -= 0.5
    if not product.price_numeric: score -= 0.4
    if not product.image_url: score -= 0.1
    if not product.brand: score -= 0.05
    return max(0.0, round(score, 2))

def _validate_product(product: CrawledProduct) -> CrawledProduct:
    product.confidence_score = _calculate_confidence(product)
    if product.confidence_score >= 0.9:
        product.validation_status = "valid"
    elif product.confidence_score >= 0.6:
        product.validation_status = "needs_review"
    else:
        product.validation_status = "invalid"
    return product

def _apply_transform(element: Tag, raw: str, transform: Optional[str]) -> str:
    val = (raw or "").strip()
    if not transform:
        return val
    t = transform.lower().strip()
    if t in ("text_content", "strip_html"):
        return val
    if t == "clean_price":
        return _clean_price(val)
    if t == "extract_percentage":
        return _extract_percentage(val)
    if t == "extract_volume_ml":
        return _extract_volume_ml(val)
    if t == "check_for_sold_out_indicator":
        return _check_sold_out(element, val)
    return val


# ── Core Crawler ───────────────────────────────────────────────────────────────

class TemplateCrawler:
    """
    Crawl listing pages và product pages theo structure được generate bởi LLM.

    Usage:
        crawler = TemplateCrawler(
            base_url="https://ruoutot.net/",
            structure=structure_dict,
            generator=structure_gen,
        )
        urls = crawler.crawl_listing("https://ruoutot.net/ruou", max_pages=20)
        products = crawler.crawl_product("https://ruoutot.net/san-pham/ruou-vang-abc")
    """

    def __init__(
        self,
        base_url: str,
        structure: dict,
        generator: Optional[StructureGenerator] = None,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
        max_retries: int = 3,
        fallback_threshold: int = 3,
    ):
        self.base_url = base_url
        self.structure = structure
        self.generator = generator or StructureGenerator()
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.fallback_threshold = fallback_threshold  # số products thất bại trước khi trigger fallback

        self.domain = urlparse(base_url).netloc
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

        # Tracking
        self._pages_crawled = 0
        self._fallback_count = 0
        self._products_found = 0

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        for attempt in range(self.max_retries):
            delay = random.uniform(self.delay_min, self.delay_max)
            if attempt > 0:
                delay *= 2  # exponential backoff
            time.sleep(delay)
            try:
                resp = self._session.get(url, timeout=25)
                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "lxml")
                elif resp.status_code in (429, 503):
                    logger.warning(f"  Rate limit (attempt {attempt+1}): {url}")
                    time.sleep(10 * (attempt + 1))
                else:
                    logger.warning(f"  HTTP {resp.status_code}: {url}")
                    return None
            except requests.RequestException as e:
                logger.error(f"  ❌ Request error (attempt {attempt+1}): {e}")
        return None

    # ── Field extraction ──────────────────────────────────────────────────────

    def _extract_field(self, item: Tag, field: dict) -> str:
        selector: str = field.get("selector") or ""
        attr: Optional[str] = field.get("attr")
        transform: Optional[str] = field.get("transform")

        if not selector:
            raw = item.get_text(strip=True)
        else:
            el = item.select_one(selector)
            if el is None:
                return ""
            if attr:
                raw = el.get(attr, "") or ""
                # Lazy load fallback
                if not raw and attr == "src":
                    for fb in _LAZY_ATTRS:
                        raw = el.get(fb, "") or ""
                        if raw:
                            break
            else:
                raw = el.get_text(strip=True)

        return _apply_transform(item, raw, transform)

    def _normalize_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith(("http://", "https://")):
            return href
        return urljoin(self.base_url, href)

    # ── Listing crawler ───────────────────────────────────────────────────────

    def crawl_listing(self, listing_url: str, max_pages: int = 50) -> List[str]:
        """
        Crawl trang listing, trả về danh sách product URLs.

        Args:
            listing_url: URL trang listing/category
            max_pages: Số trang tối đa

        Returns:
            List of product page URLs
        """
        listing_cfg = self.structure.get("listing", {})
        fields_cfg = {f["name"]: f for f in listing_cfg.get("fields", [])}
        pagination = listing_cfg.get("pagination") or {}

        logger.info(f"[{self.domain}] 📋 Crawl listing: {listing_url}")

        product_urls: List[str] = []
        seen_urls: set = set()
        page_num = 1

        while page_num <= max_pages:
            url = self._build_page_url(listing_url, pagination, page_num)
            logger.info(f"  📄 Page {page_num}: {url}")

            soup = self._get(url)
            if soup is None:
                logger.warning(f"  ⚠️  Page {page_num} failed — stopping")
                break

            self._pages_crawled += 1
            page_urls = self._extract_listing_urls(soup, listing_cfg, fields_cfg)

            if not page_urls and page_num > 1:
                logger.info(f"  🏁 Empty page {page_num} — stopping")
                break

            new_count = 0
            for u in page_urls:
                norm = self._normalize_url(u)
                if norm and norm not in seen_urls:
                    seen_urls.add(norm)
                    product_urls.append(norm)
                    new_count += 1

            logger.info(f"  ✅ +{new_count} URLs (total: {len(product_urls)})")

            if not self._has_next_page(soup, pagination, page_num, max_pages):
                logger.info(f"  🏁 No next page — stopping at page {page_num}")
                break

            page_num += 1

        logger.info(f"[{self.domain}] 📊 Listing done: {len(product_urls)} product URLs")
        return product_urls

    def _extract_listing_urls(self, soup: BeautifulSoup, listing_cfg: dict, fields_cfg: dict) -> List[str]:
        container_sel = listing_cfg.get("container_selector") or ""
        item_sel = listing_cfg.get("item_selector") or ""

        if container_sel and item_sel:
            container = soup.select_one(container_sel)
            items = container.select(item_sel) if container else soup.select(item_sel)
        elif item_sel:
            items = soup.select(item_sel)
        else:
            return []

        urls = []
        url_field = fields_cfg.get("product_url")
        if not url_field:
            # Fallback: tìm tất cả links trong items
            for item in items:
                a = item.select_one("a[href]")
                if a:
                    urls.append(a.get("href", ""))
        else:
            for item in items:
                href = self._extract_field(item, url_field)
                if href:
                    urls.append(href)

        return urls

    # ── Product crawler ───────────────────────────────────────────────────────

    def crawl_product(self, product_url: str, page_num: int = 1) -> Optional[CrawledProduct]:
        """
        Crawl 1 product detail page.

        Args:
            product_url: URL của product page
            page_num: Page number (để tracking)

        Returns:
            CrawledProduct hoặc None nếu thất bại
        """
        detail_cfg = self.structure.get("product_detail", {})
        fields_cfg = {f["name"]: f for f in detail_cfg.get("fields", [])}

        soup = self._get(product_url)
        if soup is None:
            return None

        self._pages_crawled += 1

        # Thử extract bằng selectors trước
        product = self._extract_product(soup, fields_cfg, product_url, page_num)

        # Nếu không có product name → fallback LLM
        if not product.product_name:
            self._fallback_count += 1
            logger.info(f"  ⚠️  Fallback LLM for: {product_url}")
            html_snippet = str(soup.body)[:8000] if soup.body else str(soup)[:8000]
            llm_data = self.generator.extract_product_fallback(html_snippet)
            if llm_data:
                product = self._dict_to_product(llm_data, product_url, page_num, "llm_fallback")

        if product.product_name:
            product = _validate_product(product)
            self._products_found += 1
            return product
        return None

    def _extract_product(
        self, soup: BeautifulSoup, fields_cfg: dict, product_url: str, page_num: int
    ) -> CrawledProduct:
        # Nếu có detail config: dùng toàn bộ soup làm context
        # Nếu không có: fallback sang listing fields trên toàn page
        context = soup

        def get(name: str) -> str:
            if name not in fields_cfg:
                return ""
            return self._extract_field(context, fields_cfg[name])

        price_str = get("price")
        return CrawledProduct(
            product_name=get("product_name"),
            brand=get("brand"),
            category=get("category"),
            alcohol_percent=get("alcohol_percent"),
            volume_ml=get("volume_ml"),
            price=price_str,
            price_numeric=_price_to_float(price_str),
            old_price=get("old_price"),
            stock_status=get("stock_status"),
            rating=get("rating"),
            review_count=get("review_count"),
            image_url=self._normalize_url(get("image_url")),
            product_url=product_url,
            source_site=self.domain,
            page_number=page_num,
            extraction_method="selector",
        )

    def _dict_to_product(
        self, d: dict, product_url: str, page_num: int, method: str
    ) -> CrawledProduct:
        price_str = d.get("price", "")
        return CrawledProduct(
            product_name=d.get("product_name", ""),
            brand=d.get("brand", ""),
            category=d.get("category", ""),
            alcohol_percent=d.get("alcohol_percent", ""),
            volume_ml=d.get("volume_ml", ""),
            price=price_str,
            price_numeric=_price_to_float(price_str),
            old_price=d.get("old_price", ""),
            stock_status=d.get("stock_status", ""),
            rating=d.get("rating", ""),
            review_count=d.get("review_count", ""),
            image_url=self._normalize_url(d.get("image_url", "")),
            product_url=product_url,
            source_site=self.domain,
            page_number=page_num,
            extraction_method=method,
        )

    # ── Pagination ────────────────────────────────────────────────────────────

    def _build_page_url(self, base: str, pagination: dict, page_num: int) -> str:
        if page_num == 1:
            return base

        ptype = pagination.get("type") or ""

        if ptype == "url_param":
            param = pagination.get("page_param") or "page"
            parsed = urlparse(base)
            qs = parse_qs(parsed.query)
            qs[param] = [str(page_num)]
            new_q = urlencode({k: v[0] for k, v in qs.items()})
            return urlunparse(parsed._replace(query=new_q))

        if ptype in ("numbered", "url_pattern"):
            pattern = pagination.get("url_pattern") or ""
            if pattern:
                return pattern.replace("{n}", str(page_num))

        return base

    def _has_next_page(
        self, soup: BeautifulSoup, pagination: dict, current_page: int, page_limit: int
    ) -> bool:
        if current_page >= page_limit:
            return False

        ptype = pagination.get("type") or ""
        if not ptype or ptype == "null":
            return False

        next_sel = pagination.get("next_button_selector") or ""
        if next_sel:
            btn = soup.select_one(next_sel)
            if btn is None:
                return False
            if btn.has_attr("disabled"):
                return False
            return True

        # url_param / url_pattern: tiếp tục cho đến khi page trống
        return True

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        return {
            "pages_crawled": self._pages_crawled,
            "products_found": self._products_found,
            "fallback_count": self._fallback_count,
            "success_rate": (
                round((self._products_found - self._fallback_count) / max(self._products_found, 1), 3)
                if self._products_found > 0 else 0.0
            ),
        }

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
