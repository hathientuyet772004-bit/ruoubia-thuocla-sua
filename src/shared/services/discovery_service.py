import logging
import random
import time
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
import os

import requests
from bs4 import BeautifulSoup
from .url_service import classify_url, get_domain, normalize_url

log = logging.getLogger("collector.discovery")

@dataclass(frozen=True)
class CollectConfig:
    max_discover_pages: int = int(os.getenv("COLLECT_MAX_DISCOVER_PAGES", "50"))
    max_products_per_domain: int = int(os.getenv("COLLECT_MAX_PRODUCTS_PER_DOMAIN", "2000"))
    request_timeout_sec: int = int(os.getenv("COLLECT_REQUEST_TIMEOUT_SEC", "20"))
    min_delay_sec: float = float(os.getenv("COLLECT_MIN_DELAY_SEC", "0.5"))
    max_delay_sec: float = float(os.getenv("COLLECT_MAX_DELAY_SEC", "1.5"))
    proxies: list[str] = field(
        default_factory=lambda: [p.strip() for p in os.getenv("PROXY_URLS", "").split(",") if p.strip()]
    )

class DiscoveryService:
    """
    [SOLID: Single Responsibility Principle]
    Chịu trách nhiệm duy nhất: Khám phá URL thông minh từ Sitemap hoặc duyệt rễ (BFS).
    Tách biệt hoàn toàn khỏi logic kéo dữ liệu MHTML, MinIO hay gọi PostgreSQL.
    """
    
    @staticmethod
    def _sleep_polite(cfg: CollectConfig) -> None:
        time.sleep(random.uniform(cfg.min_delay_sec, cfg.max_delay_sec))

    @staticmethod
    def _pick_proxy(cfg: CollectConfig) -> str | None:
        if not cfg.proxies:
            return None
        return random.choice(cfg.proxies)

    @staticmethod
    def _fetch(url: str, *, cfg: CollectConfig) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
        }
        proxy = DiscoveryService._pick_proxy(cfg)
        proxies = {"http": proxy, "https": proxy} if proxy else None
        resp = requests.get(url, headers=headers, timeout=cfg.request_timeout_sec, proxies=proxies)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _discover_from_sitemap(base_url: str, *, cfg: CollectConfig) -> set[str]:
        candidates = []
        parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
        root = f"{parsed.scheme}://{parsed.netloc}"
        candidates.append(urljoin(root, "/sitemap.xml"))
        candidates.append(urljoin(root, "/sitemap_index.xml"))

        urls: set[str] = set()
        for sm in candidates:
            try:
                xml = DiscoveryService._fetch(sm, cfg=cfg)
            except Exception:
                continue

            try:
                soup = BeautifulSoup(xml, "xml")
                for loc in soup.find_all("loc"):
                    u = (loc.get_text() or "").strip()
                    if u and get_domain(u) == get_domain(base_url):
                        urls.add(u)
            except Exception:
                continue

        # sitemap may include sitemap children; fetch a bit more (bounded)
        expanded: set[str] = set()
        for u in list(urls)[: min(len(urls), 10)]:
            if u.endswith(".xml") and "sitemap" in u.lower():
                try:
                    xml = DiscoveryService._fetch(u, cfg=cfg)
                    soup = BeautifulSoup(xml, "xml")
                    for loc in soup.find_all("loc"):
                        uu = (loc.get_text() or "").strip()
                        if uu and get_domain(uu) == get_domain(base_url):
                            expanded.add(uu)
                except Exception:
                    pass

        urls |= expanded
        return urls

    @staticmethod
    def _extract_links(html: str, base_url: str) -> set[str]:
        soup = BeautifulSoup(html, "lxml")
        out: set[str] = set()
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href or href.startswith(("javascript:", "#", "mailto:", "tel:", "data:")):
                continue
            out.add(urljoin(base_url, href))
        return out

    @staticmethod
    def discover_product_urls(base_url: str, *, cfg: CollectConfig) -> list[str]:
        base_url = base_url.strip()
        if not base_url:
            return []

        base_domain = get_domain(base_url)
        discovered: set[str] = set()

        for u in DiscoveryService._discover_from_sitemap(base_url, cfg=cfg):
            if get_domain(u) == base_domain and classify_url(u) == "product":
                discovered.add(u)

        queue: list[str] = [base_url]
        seen: set[str] = set()
        while queue and len(seen) < cfg.max_discover_pages and len(discovered) < cfg.max_products_per_domain:
            url = queue.pop(0)
            norm = normalize_url(url)
            if norm in seen:
                continue
            seen.add(norm)

            try:
                html = DiscoveryService._fetch(url, cfg=cfg)
            except Exception:
                continue
            DiscoveryService._sleep_polite(cfg)

            links = DiscoveryService._extract_links(html, url)
            for link in links:
                if get_domain(link) != base_domain:
                    continue
                t = classify_url(link)
                if t == "product":
                    discovered.add(link)
                    if len(discovered) >= cfg.max_products_per_domain:
                        break
                elif t in {"category", "search", "other"} and len(queue) < cfg.max_discover_pages * 3:
                    queue.append(link)

        return sorted(discovered)
