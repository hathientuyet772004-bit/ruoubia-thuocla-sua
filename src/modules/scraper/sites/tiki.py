"""
Tiki.vn scraper — dùng public REST API
Categories: sua (sữa), ruou-bia (rượu bia)
"""
import httpx
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "x-guest-token": "",
}

CATEGORY_MAP = {
    "sua": {"keyword": "sữa", "category_id": 2653},
    "ruou-bia": {"keyword": "rượu bia", "category_id": 751},
    "thuoc-la": {"keyword": "thuốc lá"},
}


async def fetch_products(category: str, limit: int = 20) -> dict:
    cfg = CATEGORY_MAP.get(category, {"keyword": category})
    keyword = cfg.get("keyword", category)
    url = "https://tiki.vn/api/v2/products"
    params = {
        "limit": limit,
        "q": keyword,
        "sort": "top_seller",
    }
    if "category_id" in cfg:
        params["category"] = cfg["category_id"]

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

    products = []
    for item in data.get("data", []):
        products.append({
            "name": item.get("name", ""),
            "brand": item.get("brand", {}).get("name", "") if item.get("brand") else "",
            "price": item.get("price", 0),
            "unit": item.get("unit_sold_percentage", ""),
            "image_url": item.get("thumbnail_url", ""),
            "product_url": f"https://tiki.vn/{item.get('url_key', '')}.html",
            "rating": item.get("rating_average", 0),
            "sold_count": item.get("quantity_sold", {}).get("value", 0) if item.get("quantity_sold") else 0,
        })

    return {
        "site": "tiki",
        "category": category,
        "products": products,
        "raw": json.dumps(data, ensure_ascii=False),
    }
