import os
import hashlib
from datetime import datetime

from src.core.config import settings


def save_bronze(site: str, url: str, content: str) -> str:
    os.makedirs(settings.bronze_dir, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{site}_{url_hash}_{timestamp}.html"
    path = os.path.join(settings.bronze_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
