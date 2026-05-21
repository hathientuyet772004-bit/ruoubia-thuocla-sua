"""
Services: URL classification, visits persistence, normalization.
Không phụ thuộc vào FastAPI — có thể test độc lập.
"""
import re
import json
from datetime import datetime
from typing import Dict
from urllib.parse import urlparse, urljoin, quote

from shared.config import settings
from db.database import SessionLocal
from models.orm import Visit


# ─── URL Helpers ──────────────────────────────────────────────────

def get_domain(url: str) -> str:
    """Trích xuất domain từ URL để tạo thư mục phân loại."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc or parsed.path.split('/')[0]
        return domain.replace("www.", "")
    except Exception:
        return "unknown"


def normalize_url(url: str) -> str:
    """
    Chuẩn hóa URL cực mạnh cho E-commerce để deduplication.
    Bỏ protocol, www, trailing slash, và PHẦN LỚN query params rác.
    """
    if not url: return ""
    
    # Bỏ protocol và www
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    
    # Tách base và params
    if '?' in url:
        base, params = url.split('?', 1)
    else:
        base, params = url, ""
        
    base = base.rstrip('/')
    
    # Danh sách các tham số quan trọng cần giữ (nếu có)
    # Thường là 'q' cho tìm kiếm, 'page' cho phân trang.
    # Với sản phẩm Shopee/Tiki/Lazada, thường chỉ cần phần base là đủ.
    keep_params = ['q', 'keyword', 'page', 'p']
    
    filtered_params = []
    if params:
        for p in params.split('&'):
            if '=' in p:
                k, v = p.split('=', 1)
                if k.lower() in keep_params:
                    filtered_params.append(f"{k}={v}")
    
    normalized = base
    if filtered_params:
        normalized += '?' + '&'.join(sorted(filtered_params))
        
    return normalized.lower()


def classify_url(url: str) -> str:
    """Phân loại URL: product / search / category / other."""
    for pattern in settings.PRODUCT_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return "product"
    for pattern in settings.SEARCH_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return "search"
    for pattern in settings.CATEGORY_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return "category"
    return "other"


def safe_filename(name: str) -> str:
    """Tạo tên file hợp lệ từ URL."""
    # Xử lý các tiền tố hay gặp
    name = re.sub(r'^https?://', '', name)
    # Thay thế các ký tự không hợp lệ cho Windows/Linux thành dấu gạch dưới
    name = re.sub(r'[^\w\.-]', '_', name)
    return name[:100]


# ─── Stats Helpers ────────────────────────────────────────────────

def get_month_key() -> str:
    return datetime.now().strftime("%Y-%m")


def format_load_time(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


# ─── Migration ────────────────────────────────────────────────────

def migrate_from_json() -> int:
    """
    Migrate data from visits.json to SQLite/Postgres.
    Returns number of records migrated.
    """
    visits_file = settings.storage_dir.parent / "collector" / "visits.json"
    if not visits_file.exists():
        return 0
    
    try:
        data = json.loads(visits_file.read_text(encoding="utf-8"))
        db = SessionLocal()
        count = 0
        
        for month_key, month_visits in data.items():
            for normalized_url, info in month_visits.items():
                # Check if already exists
                existing = db.query(Visit).filter(
                    Visit.normalized_url == normalized_url,
                    Visit.month_key == month_key
                ).first()
                
                if not existing:
                    # Convert visited_at string to datetime
                    visited_at = datetime.fromisoformat(info["visited_at"]) if "visited_at" in info else datetime.utcnow()
                    
                    visit = Visit(
                        normalized_url=normalized_url,
                        original_url=info.get("original_url", ""),
                        user_id=info.get("user_id", "anonymous"),
                        visited_at=visited_at,
                        load_time_ms=info.get("load_time_ms"),
                        page_type=info.get("page_type", "other"),
                        month_key=month_key
                    )
                    db.add(visit)
                    count += 1
        
        db.commit()
        db.close()
        return count
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return 0
