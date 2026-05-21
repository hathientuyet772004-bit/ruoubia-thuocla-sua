"""
Router: Interactive Browser Controls.
Điều khiển trình duyệt headful và thực hiện 'hút' dữ liệu.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from shared.services import BrowserManager, classify_url, normalize_url, get_month_key, safe_filename
from .pages import _get_storage_path, _save_metadata

# Note: BrowserManager is now a class, we need an instance or use shared one if defined.
# I will use BrowserManager() instance if it's not pre-instantiated in services.
browser_manager = BrowserManager() 
from datetime import datetime
from fastapi import Depends
from sqlalchemy.orm import Session
from db.database import get_db
from models.orm import Visit
from models.orm import Visit

router = APIRouter(tags=["interactive"])

class LaunchRequest(BaseModel):
    url: Optional[str] = "https://google.com"

@router.post("/browser/launch")
async def launch_browser(req: LaunchRequest):
    try:
        return await browser_manager.launch(req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/browser/status")
async def get_browser_status():
    return await browser_manager.get_status()

@router.post("/browser/navigate")
async def navigate_browser(req: LaunchRequest):
    try:
        return await browser_manager.navigate(req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/browser/collect")
async def collect_from_browser(db: Session = Depends(get_db)):
    """Lấy nội dung từ trang đang mở tại trình duyệt, lưu file và ghi log vào DB."""
    try:
        print("🔥 ĐANG CHẠY COLLECT_FROM_BROWSER (PHIÊN BẢN CHỈ LƯU MHTML) 🔥")
        data = await browser_manager.capture_current()
        url = data["url"]
        
        # 0. Ghi log vào Database để Dashboard cập nhật Stats
        norm_url = normalize_url(url)
        visit = Visit(
            normalized_url=norm_url,
            original_url=url,
            user_id="interactive_user",
            visited_at=datetime.utcnow(),
            load_time_ms=500, # Giả lập thời gian load cho interactive
            page_type=classify_url(url),
            month_key=get_month_key()
        )
        db.add(visit)
        db.commit()
        
        # Logic lưu tương tự pages.py
        directory = _get_storage_path(url)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Tạo tên file từ tiêu đề trang cho dễ đọc
        base_name = safe_filename(data["title"] or url)
        
        # Lưu MHTML
        mhtml_fname = f"{base_name}_{ts}.mhtml"
        (directory / mhtml_fname).write_text(data["mhtml"], encoding="utf-8")
        
        # Lưu Metadata
        _save_metadata(directory, mhtml_fname, url, ["interactive"], "mhtml", title=data["title"])
        
        return {
            "success": True,
            "url": url,
            "title": data["title"],
            "path": str(directory / mhtml_fname)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/browser/close")
async def close_browser():
    await browser_manager.close()
    return {"status": "closed"}
