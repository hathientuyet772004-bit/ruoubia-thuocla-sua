"""
ETL Worker — Pipeline xử lý Batch tự động thông minh.
Hệ thống tích hợp 3 lớp AI:
1. Normalizer: Chuẩn hóa tên và thương hiệu.
2. Enricher: Trích xuất thuộc tính ẩn từ mô tả.
3. DQ Guard: Kiểm soát chất lượng và tính logic của dữ liệu.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# ── Đảm bảo Python tìm được package collector/backend ─────────────────────────
# ── Setup Path to Project Root 'src' ──────────────────────────────────────────
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from sqlalchemy import text
from db.database import SessionLocal
from shared.services import download_mhtml, make_url_hash
from etl.normalizer import ProductNormalizer
from etl.enricher import ProductEnricher
from etl.dq_guard import DataQualityGuard

# ─── Logging ──────────────────────────────────────────────────────────────────
log = logging.getLogger("etl_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

# ─── Tuning ───────────────────────────────────────────────────────────────────
BATCH_SIZE = int(os.getenv("ETL_BATCH_SIZE", 20)) # Giảm batch size khi dùng nhiều AI lớp

# Khởi tạo các module AI
_normalizer = ProductNormalizer()
_enricher   = ProductEnricher()
_dq_guard   = DataQualityGuard()

def _extract_text(soup, *selectors: str, default: str = "") -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el: return el.get_text(strip=True)
    return default

def _parse_price(raw: str) -> float | None:
    if not raw: return None
    digits = re.sub(r"[^\d]", "", raw)
    return float(digits) if digits else None

def parse_mhtml_content(content: str, url: str) -> dict:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {"products": [], "branches": []}

    import email
    from email import policy
    
    html_parts = []
    msg = email.message_from_string(content, policy=policy.default)
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                html_parts.append(payload.decode(charset, errors="replace"))
    else:
        idx = content.find("<html")
        if idx != -1: html_parts.append(content[idx:])
        else: html_parts.append(content)

    if not html_parts:
        return {"products": [], "branches": []}

    # Chọn part HTML lớn nhất (thường là trang chính chứa sản phẩm)
    html_part = max(html_parts, key=len)
    soup = BeautifulSoup(html_part, "lxml")
    products = []
    
    # Baseline extraction logic
    cards = soup.select(".product, .product-item, .product-card, [class*='product-item'], [class*='ProductCard'], [class*='product-card'], article[class*='product']")
    print(f"DEBUG: Found {len(cards)} potential product cards in {url}")
    for card in cards[:50]:
        name = _extract_text(card, "[class*='name']", "[class*='title']", "h1", "h2", "h3")
        if not name:
            # Fallback: lấy text đầu tiên có vẻ là tên
            name = card.get_text(" ", strip=True)[:100]
            
        price = _extract_text(card, "[class*='price']")
        desc  = _extract_text(card, "[class*='description']", "[class*='summary']", "p")
        img = card.select_one("img")
        link = card.select_one("a")
        
        if name:
            products.append({
                "name": name,
                "price": _parse_price(price),
                "description": desc,
                "image_url": img.get("src") if img else None,
                "url": link.get("href") if link else url
            })

    # 2. AI Fallback: Sử dụng Gemini để "nhìn" và trích xuất cấu trúc nếu Baseline thất bại
    if not products:
        log.info(f"Baseline failed for {url}. Switching to AI Smart Extract...")
        try:
            prompt = f"""
            Bạn là chuyên gia trích xuất dữ liệu. Hãy tìm danh sách sản phẩm trong HTML này.
            Trích xuất tối đa 5 sản phẩm.
            Trả về JSON list: [{{"name": "...", "price": 123000, "url": "...", "image_url": "..."}}]
            HTML: {html_part[:10000]}
            """
            response = _normalizer.model.generate_content(prompt)
            text_res = response.text.strip()
            if "```json" in text_res:
                text_res = text_res.split("```json")[1].split("```")[0].strip()
            ai_prods = json.loads(text_res)
            if isinstance(ai_prods, list):
                products = ai_prods
                log.info(f"AI found {len(products)} products.")
        except Exception as e:
            log.error(f"AI Smart Extract failed: {e}")

    return {"products": products, "branches": []}

def _process_one(db, row: tuple, run_id: str) -> bool:
    file_id, url_hash, url, source, minio_path = row
    domain = (source or "unknown").strip()
    
    log.info(f"[{run_id}] 🧠 AI Pipeline: {url_hash[:8]} ({domain})")
    db.execute(text("UPDATE scraped_files SET status='processing' WHERE id=:i"), {"i": file_id})
    db.commit()

    try:
        content = download_mhtml(minio_path)
        raw_result = parse_mhtml_content(content, url)
        
        for p in raw_result["products"]:
            # Lớp 1: Chuẩn hóa tên/thương hiệu
            norm = _normalizer.normalize(p["name"], p["price"])
            clean_name = norm.get("clean_name") or p.get("name") or "Unknown Product"
            if p == raw_result["products"][0]:
                log.info(f"First product extracted: {clean_name}")
            p.update({
                "clean_name": clean_name,
                "brand": norm.get("brand"),
                "category": norm.get("standard_category")
            })

            # Lớp 2: Trích xuất thuộc tính chuyên sâu từ mô tả & ảnh (Scenario 14)
            if p.get("description") or p.get("image_url"):
                details = _enricher.enrich(
                    category=p["category"], 
                    description=p.get("description"), 
                    image_url=p.get("image_url")
                )
                p["details"] = details

            # Lớp 3: Kiểm soát chất lượng (DQ Check)
            dq_report = _dq_guard.validate_logic(p)
            p["dq_report"] = dq_report

            # Lưu vào Database
            prod_hash = make_url_hash(p.get("url") or url)
            is_ocr_v = dq_report.get("is_ocr_verified", False)
            
            db.execute(text("""
                INSERT INTO products
                    (url_hash, name, price_numeric, url, image_url, source_site, source, brand, category, raw_data, dq_report, is_verified_by_ocr, updated_at)
                VALUES
                    (:h, :n, :p, :u, :img, :s, :s, :b, :c, CAST(:r AS JSONB), CAST(:dq AS JSONB), :ov, now())
                ON CONFLICT (url_hash) DO UPDATE
                    SET name = EXCLUDED.name, price_numeric = EXCLUDED.price_numeric,
                        brand = EXCLUDED.brand, category = EXCLUDED.category,
                        raw_data = EXCLUDED.raw_data, dq_report = EXCLUDED.dq_report, 
                        is_verified_by_ocr = EXCLUDED.is_verified_by_ocr, updated_at = now()
            """), {
                "h": prod_hash, "n": p["clean_name"][:500], "p": p["price"],
                "u": p["url"], "img": p["image_url"], "s": domain,
                "b": p["brand"], "c": p["category"],
                "r": json.dumps(p, ensure_ascii=False),
                "dq": json.dumps(dq_report),
                "ov": is_ocr_v
            })

        db.execute(text("UPDATE scraped_files SET status='completed', processed_at=now() WHERE id=:i"), {"i": file_id})
        db.commit()
        return True

    except Exception as e:
        db.rollback()
        db.execute(text("UPDATE scraped_files SET status='failed', error_message=:e WHERE id=:i"), {"e": str(e), "i": file_id})
        db.commit()
        log.error(f"Error: {e}")
        return False

def run_etl_batch():
    db = SessionLocal()
    rows = db.execute(text(f"SELECT id, url_hash, url, source, minio_path FROM scraped_files WHERE status='pending' LIMIT {BATCH_SIZE}")).fetchall()
    for row in rows:
        _process_one(db, row, "BATCH-AI")
    db.close()

if __name__ == "__main__":
    run_etl_batch()
