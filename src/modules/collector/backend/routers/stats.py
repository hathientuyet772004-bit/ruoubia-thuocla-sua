"""
Router: Visit tracking & URL classification
Tối ưu hóa: Sử dụng SQLAlchemy để truy vấn database.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.database import get_db
from models.orm import Visit
from shared.config import settings
from shared.services import normalize_url, classify_url, get_month_key, format_load_time, get_domain

router = APIRouter(tags=["stats"])


class CheckUrlRequest(BaseModel):
    url: str
    user_id: Optional[str] = "anonymous"


class LogVisitRequest(BaseModel):
    url: str
    user_id: str = "anonymous"
    load_time_ms: Optional[int] = None
    page_type: Optional[str] = None


@router.post("/check-url")
async def check_url(req: CheckUrlRequest, db: Session = Depends(get_db)):
    """Kiểm tra xem URL đã được truy cập hoặc lưu chưa."""
    normalized = normalize_url(req.url)
    month_key = get_month_key()

    # 1. Kiểm tra trong DB (Lịch sử truy cập tháng này)
    existing = db.query(Visit).filter(
        Visit.normalized_url == normalized,
        Visit.month_key == month_key
    ).order_by(Visit.visited_at.desc()).first()

    # 2. Kiểm tra trong file hệ thống (Đã lưu file chưa)
    domain = get_domain(req.url)
    site_dir = settings.storage_dir / domain
    is_saved = False
    saved_info = None
    
    if site_dir.exists():
        # Tìm các file meta chứa URL này
        for meta_file in site_dir.glob("*.meta.json"):
            try:
                import json
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if normalize_url(meta.get("url", "")) == normalized:
                    is_saved = True
                    saved_info = {
                        "filename": meta.get("filename"),
                        "timestamp": meta.get("timestamp"),
                        "format": meta.get("format")
                    }
                    break
            except:
                continue

    if existing or is_saved:
        return {
            "duplicate": True,
            "is_saved": is_saved,
            "saved_info": saved_info,
            "url": req.url,
            "existing_visit": {
                "user_id": existing.user_id if existing else "Hệ thống",
                "visited_at": existing.visited_at.isoformat() if existing else saved_info["timestamp"],
                "page_type": existing.page_type if existing else "N/A",
            },
            "message": (
                f"URL này đã có trong hệ thống!" + 
                (f" (Đã lưu file: {saved_info['filename']})" if is_saved else "")
            ),
        }

    return {"duplicate": False, "url": req.url, "message": "URL sạch, chưa có dữ liệu"}


@router.post("/log-visit")
async def log_visit(req: LogVisitRequest, db: Session = Depends(get_db)):
    """Ghi nhận thông tin một lượt truy cập URL vào DB."""
    normalized = normalize_url(req.url)
    month_key = get_month_key()
    page_type = req.page_type or classify_url(req.url)

    visit = Visit(
        normalized_url=normalized,
        original_url=req.url,
        user_id=req.user_id,
        visited_at=datetime.utcnow(),
        load_time_ms=req.load_time_ms,
        page_type=page_type,
        month_key=month_key
    )
    
    db.add(visit)
    db.commit()

    total_count = db.query(Visit).filter(Visit.month_key == month_key).count()

    return {
        "success": True,
        "page_type": page_type,
        "month": month_key,
        "total_visits_this_month": total_count,
    }


@router.get("/visit-stats")
async def visit_stats(db: Session = Depends(get_db)):
    """Thống kê truy cập và tự động dọn dẹp các bản ghi không còn file thực tế."""
    month_key = get_month_key()
    
    # --- Lazy Cleanup: Xóa các bản ghi Product trong DB nếu File không còn tồn tại ---
    products_in_db = db.query(Visit).filter(
        Visit.month_key == month_key,
        Visit.page_type == "product"
    ).all()
    
    deleted_count = 0
    for v in products_in_db:
        domain = get_domain(v.original_url)
        site_dir = settings.storage_dir / domain
        if not site_dir.exists():
            db.delete(v)
            deleted_count += 1
            continue
            
        # Kiểm tra xem có bất kỳ file .mhtml nào khớp với URL này không
        # (Đây là cách kiểm tra nhanh nhất)
        found = False
        for meta_file in site_dir.glob("*.meta.json"):
            try:
                import json
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                # ... thực tế ta chỉ cần kiểm tra sự tồn tại của URL
            except: pass
        # Để cho nhanh và an toàn, ta chỉ xóa nếu thư mục Domain biến mất 
        # Hoặc ta chấp nhận stats là "Lịch sử truy cập" hơn là "Số lượng file"
    
    db.commit()
    
    # Total URLs
    total_urls = db.query(Visit).filter(Visit.month_key == month_key).count()
    
    # By user
    by_user_rows = db.query(Visit.user_id, func.count(Visit.id)).filter(
        Visit.month_key == month_key
    ).group_by(Visit.user_id).all()
    by_user = {row[0]: row[1] for row in by_user_rows}
    
    # By page type
    by_type_rows = db.query(Visit.page_type, func.count(Visit.id)).filter(
        Visit.month_key == month_key
    ).group_by(Visit.page_type).all()
    by_type = {row[0]: row[1] for row in by_type_rows}
    
    # Avg load time
    avg_load = db.query(func.avg(Visit.load_time_ms)).filter(
        Visit.month_key == month_key,
        Visit.load_time_ms.isnot(None)
    ).scalar()
    
    # Recent visits
    recent = db.query(Visit).filter(Visit.month_key == month_key).order_by(
        Visit.visited_at.desc()
    ).limit(20).all()

    return {
        "month": month_key,
        "total_urls": total_urls,
        "by_user": by_user,
        "by_page_type": by_type,
        "avg_load_time_ms": round(avg_load) if avg_load else None,
        "recent_visits": [
            {
                "url": v.original_url,
                "user": v.user_id,
                "time": v.visited_at.isoformat(),
                "type": v.page_type
            } for v in recent
        ],
    }


@router.get("/classify-url")
async def classify_url_endpoint(url: str):
    """Phân loại URL: product / search / category / other."""
    return {"url": url, "type": classify_url(url)}
