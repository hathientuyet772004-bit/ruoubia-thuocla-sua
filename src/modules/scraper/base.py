"""
Base scraper — abstract class mọi site scraper đều kế thừa.
"""
from abc import ABC, abstractmethod

import httpx

from src.core.config import settings
from src.models.product import ScrapeResult

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
}


class BaseScraper(ABC):
    site_name: str = ""
    category_urls: dict[str, str] = {}

    def get_url(self, category: str) -> str:
        url = self.category_urls.get(category)
        if not url:
            raise ValueError(f"[{self.site_name}] Unknown category: {category}")
        return url

    async def fetch_html(self, url: str, extra_headers: dict | None = None) -> str:
        headers = {**DEFAULT_HEADERS, **(extra_headers or {})}
        async with httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text

    async def fetch_json(self, url: str, params: dict | None = None, extra_headers: dict | None = None) -> dict:
        headers = {**DEFAULT_HEADERS, **(extra_headers or {})}
        async with httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    @abstractmethod
    async def scrape(self, category: str, limit: int) -> ScrapeResult:
        """Scrape products for a category. Must return ScrapeResult."""
        ...
