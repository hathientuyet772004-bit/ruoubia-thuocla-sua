import os
import hashlib
from datetime import datetime

BRONZE_DIR = os.path.join(os.path.dirname(__file__), "../../data/bronze")


def save_bronze(site: str, url: str, html: str) -> str:
    os.makedirs(BRONZE_DIR, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{site}_{url_hash}_{timestamp}.html"
    path = os.path.join(BRONZE_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
