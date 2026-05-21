import sys
import asyncio
import re

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, quote
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from shared.config import settings

async def _setup_browser_and_page(p, headless: bool = True, proxy_server: str | None = None, viewport: dict | None = None):
    """
    [SOLID: DRY & Factory Pattern]
    Abstract hóa toàn bộ logic khởi tạo cực kỳ rườm rà của Playwright vào 1 chỗ.
    Tránh việc copy-paste 20 dòng code này ở khắp mọi hàm.
    """
    viewport = viewport or settings.PLAYWRIGHT_VIEWPORT
    browser = await p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"] + (["--window-size=1280,800"] if not headless else []),
    )
    context = await browser.new_context(
        user_agent=settings.PLAYWRIGHT_USER_AGENT,
        viewport=viewport,
        proxy={"server": proxy_server} if proxy_server else None,
    )
    page = await context.new_page()
    return browser, context, page

async def fetch_html(url: str, *, proxy_server: str | None = None) -> str:
    """Fetch rendered HTML dùng Playwright (cho proxy mode)."""
    async with async_playwright() as p:
        browser, context, page = await _setup_browser_and_page(p, proxy_server=proxy_server)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=settings.PLAYWRIGHT_TIMEOUT_MS)
            await page.wait_for_timeout(settings.PLAYWRIGHT_WAIT_MS)
            html = await page.content()
        except Exception as e:
            html = f"<html><body><h1>Lỗi tải trang: {e}</h1></body></html>"
        finally:
            await browser.close()
    return html

class ProxyPatcher:
    """[SOLID: Single Responsibility] Tách logic xử lý chuỗi Proxy ra thành class riêng biệt."""
    @staticmethod
    def rewrite_links(html: str, base_url: str, proxy_base: str) -> str:
        def rewrite_url(href: str) -> str:
            if not href or any(href.startswith(p) for p in ("javascript", "#", "data:")):
                return href
            try:
                absolute = urljoin(base_url, href)
                if absolute.startswith(("http://", "https://")):
                    return proxy_base + quote(absolute, safe="")
            except Exception:
                pass
            return href

        def replace_attr(m):
            attr, quote_char, val = m.group(1), m.group(2), m.group(3)
            return f'{attr}={quote_char}{rewrite_url(val)}{quote_char}'

        return re.sub(r'(href|action|src)=(["\'])([^"\']*)\2', replace_attr, html, flags=re.IGNORECASE)

    @staticmethod
    def inject_script(html: str, base_url: str) -> str:
        base_tag = f'<base href="{base_url}">'
        anti_redirect = (
            '<script>try{'
            'Object.defineProperty(window,"top",{get:function(){return window;}});'
            'Object.defineProperty(window,"parent",{get:function(){return window;}});'
            '}catch(e){}</script>'
        )
        inject = base_tag + anti_redirect
        return re.sub(r'(<head[^>]*>)', r'\1' + inject, html, flags=re.IGNORECASE, count=1)

async def fetch_mhtml(url: str, *, proxy_server: str | None = None, behaviors: list = None) -> tuple[str, str]:
    """Snapshot trang dưới dạng MHTML (cho background save), hỗ trợ cắm thêm Plugins (Behaviors)."""
    async with async_playwright() as p:
        browser, context, page = await _setup_browser_and_page(
            p, proxy_server=proxy_server, viewport={"width": 1920, "height": 1080}
        )
        
        if behaviors:
            for behavior in behaviors:
                behavior.attach(page)

        try:

            await page.goto(url, wait_until="domcontentloaded", timeout=settings.PLAYWRIGHT_TIMEOUT_MS)
            await page.wait_for_timeout(5000)
            title = await page.title()
            cdp = await page.context.new_cdp_session(page)
            result = await cdp.send("Page.captureSnapshot", {"format": "mhtml"})
            mhtml_content = result["data"]
        finally:
            await browser.close()
    return mhtml_content, title


class BrowserManager:
    def __init__(self):
        self.pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._lock = asyncio.Lock()

    async def launch(self, url: str = "https://google.com"):
        async with self._lock:
            if not self.pw:
                self.pw = await async_playwright().start()
            
            if not self.browser:
                self.browser, self.context, self.page = await _setup_browser_and_page(
                    self.pw, headless=False
                )
            
            await self.page.goto(url)
            return {"status": "launched", "url": self.page.url}

    async def navigate(self, url: str):
        if not self.page:
            return await self.launch(url)
        await self.page.goto(url)
        return {"status": "navigated", "url": self.page.url}

    async def get_status(self):
        if not self.page:
            return {"active": False}
        try:
            return {
                "active": True,
                "url": self.page.url,
                "title": await self.page.title()
            }
        except:
            return {"active": False}

    async def capture_current(self):
        """Chụp dữ liệu từ trang đang mở tại trình duyệt."""
        if not self.page:
            raise Exception("Trình duyệt chưa được mở.")
        
        url = self.page.url
        title = await self.page.title()
        
        # Snapshot MHTML qua CDP
        cdp = await self.page.context.new_cdp_session(self.page)
        res = await cdp.send("Page.captureSnapshot", {"format": "mhtml"})
        mhtml_content = res["data"]
        
        # Lấy HTML thuần nữa để chắc chắn
        html_content = await self.page.content()
        
        return {
            "url": url,
            "title": title,
            "html": html_content,
            "mhtml": mhtml_content
        }

    async def close(self):
        async with self._lock:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.pw:
                await self.pw.stop()
                self.pw = None
            self.page = None

# Instance duy nhất cho toàn bộ app
browser_manager = BrowserManager()
