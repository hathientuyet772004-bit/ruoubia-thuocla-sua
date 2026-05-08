"""WinMart scraper — HTTP + BeautifulSoup."""
from bs4 import BeautifulSoup

from src.models.product import Product, ScrapeResult
from src.modules.scraper.base import BaseScraper

BASE_URL = "https://winmart.vn"


class WinMartScraper(BaseScraper):
    site_name = "winmart"
    category_urls = {
        "sua":      f"{BASE_URL}/danh-muc/sua-va-san-pham-tu-sua",
        "ruou-bia": f"{BASE_URL}/danh-muc/bia-ruou",
        "thuoc-la": f"{BASE_URL}/danh-muc/thuoc-la",
    }

    async def scrape(self, category: str, limit: int = 20) -> ScrapeResult:
        url = self.get_url(category)
        html = await self.fetch_html(url)
        products = self._parse(html, limit)
        return ScrapeResult(
            site=self.site_name,
            category=category,
            products=products,
            raw=html[:50_000],
        )

    def _parse(self, html: str, limit: int) -> list[Product]:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select(".product-card, .product-item, [class*='product']")[:limit]
        results = []
        for item in items:
            name_el  = item.select_one("h3, h2, .product-name, [class*='name']")
            price_el = item.select_one(".price, [class*='price']")
            img_el   = item.select_one("img")
            link_el  = item.select_one("a")

            name = (name_el.get_text(strip=True) if name_el else "").strip()
            if not name:
                continue

            price_raw = price_el.get_text(strip=True) if price_el else ""
            img   = (img_el.get("src") or img_el.get("data-src", "")) if img_el else ""
            href  = link_el.get("href", "") if link_el else ""
            if href and not href.startswith("http"):
                href = BASE_URL + href

            results.append(Product(
                name=name,
                price=price_raw,
                image_url=img,
                product_url=href,
            ))
        return results
