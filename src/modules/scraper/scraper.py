"""Phase 2 — SmartScraper: requests + BeautifulSoup scraper driven by a
structure dict produced by analyzer.analyze_page_structure().
"""
from __future__ import annotations

import time
from dataclasses import asdict
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlunparse, urlencode

import asyncio
from bs4 import BeautifulSoup, Tag
from shared.config import settings
from shared.services import fetch_html, get_domain
from .models import Branch, CompanyProfile, Product
from .transforms import apply_transform, price_to_float

# Lazy-load attribute fallbacks tried in order when attr="src"
_LAZY_ATTRS = ("data-lazy", "data-src", "data-original", "data-url")


class SmartScraper:
    """Scrape products, branches, and company profile using a structure dict."""

    def __init__(self, base_url: str, structure: dict, delay: float = 1.5):
        self.base_url = base_url
        self.structure = structure
        self.delay = delay
        self.site_name = get_domain(base_url)

        # Index crawl_targets by entity name for O(1) lookup
        self._targets: dict[str, dict] = {
            t["entity"]: t
            for t in structure.get("crawl_targets", [])
            if t.get("entity")
        }

    # ── HTTP (Refactored to use shared service) ──────────────────────────────

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        if self.delay > 0:
            time.sleep(self.delay)
        try:
            # Note: SmartScraper is currently sync, but our fetch_html is async.
            html = asyncio.run(fetch_html(url)) 
            return BeautifulSoup(html, "lxml")
        except Exception as exc:
            print(f"    ❌ Error fetching {url}: {exc}")
            return None

    # ── Field extraction ─────────────────────────────────────────────────────

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
                # Fallback for lazy-loaded images
                if not raw and attr == "src":
                    for fb in _LAZY_ATTRS:
                        raw = el.get(fb, "") or ""
                        if raw:
                            break
            else:
                raw = el.get_text(strip=True)

        return apply_transform(item, raw, transform)

    def _normalize_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            return href
        return urljoin(self.base_url, href)

    # ── Item list from page ───────────────────────────────────────────────────

    def _get_items(self, soup: BeautifulSoup, target: dict) -> List[Tag]:
        container_sel: str = target.get("container_selector") or ""
        item_sel: str = target.get("item_selector") or ""

        if container_sel and item_sel:
            container = soup.select_one(container_sel)
            if container:
                return container.select(item_sel)
            return soup.select(item_sel)  # graceful fallback
        if item_sel:
            return soup.select(item_sel)
        if container_sel:
            return soup.select(container_sel)
        return []

    # ── Products ─────────────────────────────────────────────────────────────

    def _parse_products_from_page(
        self, soup: BeautifulSoup, page_number: int
    ) -> List[Product]:
        target = self._targets.get("products", {})
        if not target:
            return []

        fields_cfg: dict[str, dict] = {
            f["name"]: f for f in target.get("fields", [])
        }

        def get(item: Tag, name: str) -> str:
            return (
                self._extract_field(item, fields_cfg[name])
                if name in fields_cfg
                else ""
            )

        results: List[Product] = []
        for item in self._get_items(soup, target):
            price_str = get(item, "price")
            p = Product(
                product_name=get(item, "product_name"),
                brand=get(item, "brand"),
                category=get(item, "category"),
                alcohol_percent=get(item, "alcohol_percent"),
                volume_ml=get(item, "volume_ml"),
                price=price_str,
                price_numeric=price_to_float(price_str),
                old_price=get(item, "old_price"),
                stock_status=get(item, "stock_status"),
                rating=get(item, "rating"),
                review_count=get(item, "review_count"),
                image_url=self._normalize_url(get(item, "image_url")),
                product_url=self._normalize_url(get(item, "product_url")),
                source_site=self.site_name,
                page_number=page_number,
            )
            if p.product_name:
                results.append(p)
        return results

    # ── Branches ─────────────────────────────────────────────────────────────

    def _parse_branches_from_page(self, soup: BeautifulSoup) -> List[Branch]:
        target = self._targets.get("branches", {})
        if not target or (
            not target.get("container_selector") and not target.get("item_selector")
        ):
            return []

        fields_cfg: dict[str, dict] = {
            f["name"]: f for f in target.get("fields", [])
        }

        def get(item: Tag, name: str) -> str:
            return (
                self._extract_field(item, fields_cfg[name])
                if name in fields_cfg
                else ""
            )

        results: List[Branch] = []
        for item in self._get_items(soup, target):
            b = Branch(
                branch_name=get(item, "branch_name"),
                branch_url=self._normalize_url(get(item, "branch_url")),
                address=get(item, "address"),
                phone=get(item, "phone"),
                email=get(item, "email"),
                source_site=self.site_name,
            )
            if b.branch_name:
                results.append(b)
        return results

    # ── Company profile ───────────────────────────────────────────────────────

    def _parse_company_profile_from_page(
        self, soup: BeautifulSoup
    ) -> Optional[CompanyProfile]:
        target = self._targets.get("company_profile", {})
        if not target or not target.get("container_selector"):
            return None

        fields_cfg: dict[str, dict] = {
            f["name"]: f for f in target.get("fields", [])
        }

        container_sel: str = target.get("container_selector") or ""
        container = soup.select_one(container_sel) if container_sel else soup
        if container is None:
            return None

        def get(name: str) -> str:
            return (
                self._extract_field(container, fields_cfg[name])
                if name in fields_cfg
                else ""
            )

        cp = CompanyProfile(
            company_name=get("company_name"),
            company_address=get("company_address"),
            company_phone=get("company_phone"),
            company_email=get("company_email"),
            company_logo=self._normalize_url(get("company_logo")),
            source_site=self.site_name,
        )
        return cp if any(
            [cp.company_name, cp.company_address, cp.company_phone]
        ) else None

    # ── Pagination ────────────────────────────────────────────────────────────

    def _get_pagination(self) -> dict:
        products_target = self._targets.get("products", {})
        pg = products_target.get("pagination") or {}
        if pg:
            return pg
        return self.structure.get("pagination") or {}

    def _build_page_url(self, page_num: int) -> str:
        pg = self._get_pagination()
        ptype: str = pg.get("type") or ""

        if ptype == "url_param":
            param = pg.get("page_param") or "page"
            parsed = urlparse(self.base_url)
            qs = parse_qs(parsed.query)
            qs[param] = [str(page_num)]
            new_query = urlencode({k: v[0] for k, v in qs.items()})
            return urlunparse(parsed._replace(query=new_query))

        if ptype in ("url_pattern", "numbered"):
            pattern = pg.get("url_pattern") or ""
            if pattern:
                return pattern.replace("{n}", str(page_num))

        return self.base_url

    def _has_next_page(
        self, soup: BeautifulSoup, current_page: int, page_limit: int
    ) -> bool:
        if current_page >= page_limit:
            return False

        pg = self._get_pagination()
        ptype: str = pg.get("type") or ""
        if not ptype or ptype == "null":
            return False

        next_sel: str = pg.get("next_button_selector") or ""
        if next_sel:
            btn = soup.select_one(next_sel)
            if btn is None:
                return False
            if btn.has_attr("disabled"):
                return False
            parent = btn.parent
            if parent and "disabled" in parent.get("class", []):
                return False
            return True

        # For url_param / url_pattern: assume more pages until empty result
        return True

    # ── Public API ────────────────────────────────────────────────────────────

    def scrape_page(
        self, url: str, page_num: int = 1
    ) -> Tuple[List[Product], List[Branch], Optional[CompanyProfile]]:
        """Scrape a single page. Returns (products, branches, company_profile)."""
        soup = self._get(url)
        if soup is None:
            return [], [], None

        products = self._parse_products_from_page(soup, page_num)
        branches = self._parse_branches_from_page(soup)
        company = self._parse_company_profile_from_page(soup)
        return products, branches, company

    def scrape_all(self, max_pages: int = 50) -> dict:
        """Scrape all pages and return aggregated, deduplicated results."""
        print(f"\n🚀 Starting scrape: {self.base_url}")
        pg = self._get_pagination()
        print(f"   Pagination type: {pg.get('type') or 'none'}")

        all_products: List[Product] = []
        all_branches: List[Branch] = []
        company_profile: Optional[CompanyProfile] = None
        pages_scraped = 0

        for page_num in range(1, max_pages + 1):
            url = self._build_page_url(page_num)
            print(f"   📄 Page {page_num}: {url}")

            soup = self._get(url)
            if soup is None:
                break

            products = self._parse_products_from_page(soup, page_num)
            branches = self._parse_branches_from_page(soup)
            cp = self._parse_company_profile_from_page(soup)

            all_products.extend(products)
            all_branches.extend(branches)
            if cp and company_profile is None:
                company_profile = cp

            pages_scraped = page_num
            print(
                f"      ✅ +{len(products)} products, +{len(branches)} branches"
            )

            # Stop if a url_param/url_pattern page returns zero products
            if len(products) == 0 and page_num > 1:
                print(f"   🏁 Empty page {page_num} — stopping.")
                break

            if not self._has_next_page(soup, page_num, max_pages):
                print(f"   🏁 No next page at page {page_num}.")
                break

        # Deduplicate
        seen_products: dict[str, Product] = {}
        for p in all_products:
            key = (p.product_url or p.product_name).lower().strip()
            if key and key not in seen_products:
                seen_products[key] = p

        seen_branches: dict[str, Branch] = {}
        for b in all_branches:
            key = (b.branch_name + b.address).lower().strip()
            if key and key not in seen_branches:
                seen_branches[key] = b

        unique_products = list(seen_products.values())
        unique_branches = list(seen_branches.values())

        print(
            f"\n📊 Results: {len(unique_products)} products, "
            f"{len(unique_branches)} branches"
        )

        return {
            "products": unique_products,
            "branches": unique_branches,
            "company_profile": company_profile,
            "total_products": len(unique_products),
            "total_branches": len(unique_branches),
            "pages_scraped": pages_scraped,
            "source_site": self.site_name,
        }
