"""
Headless Scroll Behavior — Xử lý cuộn trang vô tận và nút 'Tải thêm'.
Sử dụng chung cho các website SPA/Infinite Scroll.
"""
import logging
from playwright.async_api import Page

log = logging.getLogger("shared.behaviors.scroll")

async def scroll_to_bottom(page: Page, max_scrolls: int = 15, scroll_pause_ms: int = 1000):
    """Thực hiện cuộn trang đến khi không còn dữ liệu mới hoặc đạt giới hạn."""
    prev_height = await page.evaluate("document.body.scrollHeight")
    for i in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(scroll_pause_ms)
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == prev_height:
            log.info(f"✨ Đã cuộn hết trang sau {i+1} lần.")
            break
        prev_height = new_height
    return page
