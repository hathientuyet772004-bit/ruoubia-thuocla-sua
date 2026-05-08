"""Tiki.vn scraper — public REST API."""
from src.models.product import Product, ScrapeResult
from src.modules.scraper.base import BaseScraper

API_URL = "https://tiki.vn/api/v2/products"

CATEGORY_MAP = {
    "sua":      {"q": "sữa",      "category": 2653},
    "ruou-bia": {"q": "rượu bia", "category": 751},
    "thuoc-la": {"q": "thuốc lá"},
}


class TikiScraper(BaseScraper):
    site_name = "tiki"

    async def scrape(self, category: str, limit: int = 20) -> ScrapeResult:
        cfg = CATEGORY_MAP.get(category, {"q": category})
        params = {"limit": limit, "q": cfg["q"], "sort": "top_seller"}
        if "category" in cfg:
            params["category"] = cfg["category"]

        data = await self.fetch_json(
            API_URL,
            params=params,
            extra_headers={"Accept": "application/json"},
        )

        products = [
            Product(
                name=item.get("name", ""),
                brand=(item.get("brand") or {}).get("name", ""),
                price=item.get("price", 0),
                unit="",
                image_url=item.get("thumbnail_url", ""),
                product_url=f"https://tiki.vn/{item.get('url_key', '')}.html",
                rating=item.get("rating_average", 0),
                sold_count=(item.get("quantity_sold") or {}).get("value", 0),
            )
            for item in data.get("data", [])
            if item.get("name")
        ]

        return ScrapeResult(
            site=self.site_name,
            category=category,
            products=products,
            raw=str(data)[:50_000],
        )
