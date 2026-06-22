import pymongo
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import uuid
from datetime import datetime, timezone

client = pymongo.MongoClient("mongodb://mongodb:27017/")
db = client["auto_collection_data_marketing"]

# Clear old products
db.sc_products.delete_many({"domain": "thegioisua.com"})
db.sc_offers.delete_many({"domain": "thegioisua.com"})

url = "https://thegioisua.com/sua-tuoi"
req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urlopen(req, timeout=10) as resp:
        html = resp.read()

    soup = BeautifulSoup(html, "html.parser")
    products = []
    
    # Selector heuristics
    items = soup.select(".item-product, .product-item, .product-block, .item")
    for item in items:
        name_el = item.select_one(".name a, .product-name a, h3 a")
        price_el = item.select_one(".price, .special-price, .product-price")
        
        if not name_el:
            continue
            
        name = name_el.text.strip()
        link = name_el.get("href", "")
        if link and not link.startswith("http"):
            link = "https://thegioisua.com" + link
            
        price_str = price_el.text.strip() if price_el else "0"
        price_num = "".join(filter(str.isdigit, price_str))
        price = float(price_num) if price_num else 0

        # Insert product
        products.append({
            "product_id": str(uuid.uuid4()),
            "domain": "thegioisua.com",
            "product_name": name,
            "price_numeric": price,
            "url": link,
            "category": "Sữa Tươi",
            "store_name": "Thế Giới Sữa",
            "source": "thegioisua.com",
            "updated_at": datetime.now(timezone.utc)
        })

    if products:
        db.sc_products.insert_many(products)
        
        for p in products:
            db.sc_offers.insert_one({
                "domain": p["domain"],
                "product_name": p["product_name"],
                "price_numeric": p["price_numeric"],
                "url": p["url"],
                "updated_at": p["updated_at"]
            })
            
        print(f"Successfully scraped and inserted {len(products)} real products from thegioisua.com!")
    else:
        print("No products found using the current selectors.")

except Exception as e:
    print(f"Error scraping data: {e}")
