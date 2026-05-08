"""
WinMart scraper — HTTP + BeautifulSoup
"""
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi-VN,vi;q=0.9",
}

CATEGORY_URLS = {
    "sua": "https://winmart.vn/danh-muc/sua-va-san-pham-tu-sua",
    "ruou-bia": "https://winmart.vn/danh-muc/bia-ruou",
    "thuoc-la": "https://winmart.vn/danh-muc/thuoc-la",
}


async def fetch_products(category: str, limit: int = 20) -> dict:
    url = CATEGORY_URLS.get(category, CATEGORY_URLS["sua"])
    html_content = ""

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        html_content = resp.text

    soup = BeautifulSoup(html_content, "lxml")
    products = []

    items = soup.select(".product-card, .product-item, [class*='product']")[:limit]

    for item in items:
        name_el = item.select_one("h3, h2, .product-name, [class*='name']")
        price_el = item.select_one(".price, [class*='price']")
        img_el = item.select_one("img")
        link_el = item.select_one("a")

        name = name_el.get_text(strip=True) if name_el else ""
        price_text = price_el.get_text(strip=True) if price_el else "0"
        price_clean = "".join(c for c in price_text if c.isdigit())
        price = int(price_clean) if price_clean else 0
        img = img_el.get("src", img_el.get("data-src", "")) if img_el else ""
        link = link_el.get("href", "") if link_el else ""
        if link and not link.startswith("http"):
            link = "https://winmart.vn" + link

        if name:
            products.append({
                "name": name,
                "brand": "",
                "price": price,
                "unit": "",
                "image_url": img,
                "product_url": link,
                "rating": 0,
                "sold_count": 0,
            })

    return {
        "site": "winmart",
        "category": category,
        "products": products,
        "raw": html_content[:50000],
    }
