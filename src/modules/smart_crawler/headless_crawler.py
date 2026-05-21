"""
HeadlessCrawler — Crawl các trang SPA/Dynamic dùng Playwright.
Hỗ trợ:
  - Infinite scroll
  - Load More buttons
  - Chờ page render hoàn toàn
"""
from __future__ import annotations

import time
import logging
import random
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright, Browser, Page
from bs4 import BeautifulSoup

from .template_crawler import TemplateCrawler, CrawledProduct, _price_to_float

logger = logging.getLogger("smart_crawler.headless_crawler")

class HeadlessCrawler(TemplateCrawler):
    """
    Kế thừa TemplateCrawler nhưng thay thế cơ chế fetch bằng Playwright.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser: Optional[Browser] = None
        self.playwright = None

    def _init_browser(self):
        if not self.browser:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)

    def _get_page_content(self, url: str, strategy: str = "scroll", max_scrolls: int = 15) -> Optional[str]:
        self._init_browser()
        context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            logger.info(f"  🎭 Playwright: Navigating to {url}")
            # Thêm timeout dài hơn cho các trang market
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Xử lý các nốt popup hoặc chọn vị trí nếu là các trang market Việt Nam
            self._handle_initial_popups(page, url)

            if strategy == "scroll":
                self._infinite_scroll(page, max_scrolls)
            elif strategy == "load_more":
                self._click_load_more(page)
            
            # Đợi thêm một chút để các ảnh/giá lazy load hiện ra
            page.wait_for_timeout(2000)
            
            content = page.content()
            context.close()
            return content
        except Exception as e:
            logger.error(f"  ❌ Playwright error fetching {url}: {e}")
            context.close()
            return None

    def _handle_initial_popups(self, page: Page, url: str):
        """Xử lý các popup chọn khu vực hoặc quảng cáo của Lotte/BHX/WinMart."""
        domain = urlparse(url).netloc
        
        try:
            if "bachhoaxanh.com" in domain:
                # Thường có popup chọn địa chỉ
                # Thử tìm nút 'Đóng' hoặc chọn đại một khu vực nếu hiện ra
                page.wait_for_timeout(2000)
                # Ví dụ: chọn Hồ Chí Minh nếu có popup
                # (Đây là ví dụ, thực tế cần check selector chính xác)
                pass
            
            if "lottemart.vn" in domain:
                # Đợi nút chọn vị trí
                pass
        except:
            pass

    def _infinite_scroll(self, page: Page, max_scrolls: int):
        prev_height = 0
        for i in range(max_scrolls):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break
            prev_height = new_height
            logger.info(f"    📜 Scrolled {i+1}/{max_scrolls}")

    def _click_load_more(self, page: Page):
        # Lấy selector từ structure nếu có
        pg = self.structure.get("listing", {}).get("pagination", {})
        selector = pg.get("next_button_selector")
        
        if not selector:
            return

        click_count = 0
        while click_count < 20:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2000)
                    click_count += 1
                    logger.info(f"    🖱️ Clicked Load More x{click_count}")
                else:
                    break
            except:
                break

    # Override lại crawl_listing để dùng Playwright
    def crawl_listing(self, listing_url: str, max_pages: int = 1) -> List[str]:
        # Đối với headless, thường chúng ta load 1 trang nhưng scroll nhiều lần
        # Thay vì loop qua từng page URL như template_crawler
        
        strategy = "scroll"
        pg_type = self.structure.get("listing", {}).get("pagination", {}).get("type")
        if pg_type == "load_more":
            strategy = "load_more"

        html = self._get_page_content(listing_url, strategy=strategy)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        self._pages_crawled += 1
        
        listing_cfg = self.structure.get("listing", {})
        fields_cfg = {f["name"]: f for f in listing_cfg.get("fields", [])}
        
        urls = self._extract_listing_urls(soup, listing_cfg, fields_cfg)
        logger.info(f"[{self.domain}] ✅ Headless extraction: Found {len(urls)} URLs")
        
        return [self._normalize_url(u) for u in urls]

    # Override crawl_product để dùng Playwright (nếu cần render dynamic content trong detail)
    def crawl_product(self, product_url: str, page_num: int = 1) -> Optional[CrawledProduct]:
        # Thử fetch bằng requests trước cho nhanh, nếu không có data mới dùng Playwright
        # Hoặc cấu hình luôn dùng Playwright nếu domain nằm trong danh sách "hard"
        
        html = self._get_page_content(product_url, strategy="none")
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        self._pages_crawled += 1
        
        detail_cfg = self.structure.get("product_detail", {})
        fields_cfg = {f["name"]: f for f in detail_cfg.get("fields", [])}
        
        product = self._extract_product(soup, fields_cfg, product_url, page_num)
        
        if product.product_name:
            self._products_found += 1
            return product
        return None

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        super().close()
