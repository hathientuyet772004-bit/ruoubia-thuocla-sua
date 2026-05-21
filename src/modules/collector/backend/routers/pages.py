"""
Router: Pages — Lưu trang và quản lý file đã lưu
Tối ưu: Lưu file vào thư mục phân loại theo domain.
"""
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.database import get_db

from shared.config import settings
from shared.services import classify_url, safe_filename, get_domain, fetch_mhtml, normalize_url

router = APIRouter(tags=["pages"])


class SaveRequest(BaseModel):
    url: str
    html: str
    filename: Optional[str] = None
    tags: Optional[List[str]] = []


class SaveMhtmlRequest(BaseModel):
    url: str
    filename: Optional[str] = None
    tags: Optional[List[str]] = []


def _get_storage_path(url: str) -> str:
    """Tạo thư mục con cho domain và trả về đường dẫn."""
    domain = get_domain(url)
    site_dir = settings.storage_dir / domain
    site_dir.mkdir(exist_ok=True, parents=True)
    return site_dir


def _save_metadata(directory, fname: str, url: str, tags: list, fmt: str, title: str = None) -> None:
    print(f"📄 Đang lưu metadata cho {fname} - Tiêu đề: {title}")
    metadata = {
        "url": url,
        "title": title or "Unknown Page",
        "filename": fname,
        "timestamp": datetime.now().isoformat(),
        "tags": tags,
        "page_type": classify_url(url),
        "format": fmt,
    }
    meta_path = directory / f"{fname}.meta.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/save")
async def save_page(req: SaveRequest):
    try:
        directory = _get_storage_path(req.url)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = safe_filename(req.filename or req.url)
        fname = f"{base}_{ts}.html"
        
        file_path = directory / fname
        file_path.write_text(req.html, encoding="utf-8")
        
        _save_metadata(directory, fname, req.url, req.tags or [], "html", title=req.filename)
        return {"success": True, "filename": fname, "path": str(file_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-mhtml")
async def save_mhtml(req: SaveMhtmlRequest):
    print(f"📥 Bắt đầu lưu MHTML: {req.url}")
    try:
        directory = _get_storage_path(req.url)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        mhtml_content, title = await fetch_mhtml(req.url)
        
        # Ưu tiên lấy title trang làm tên file cho dễ nhìn
        base = safe_filename(title or req.filename or req.url)
        fname = f"{base}_{ts}.mhtml"

        file_path = directory / fname
        file_path.write_text(mhtml_content, encoding="utf-8")
        
        _save_metadata(directory, fname, req.url, req.tags or [], "mhtml", title=title)

        size = file_path.stat().st_size
        return {"success": True, "filename": fname, "path": str(file_path), "size": size, "format": "mhtml"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu MHTML: {e}")


@router.delete("/saved/{filename}")
async def delete_item(filename: str, db: Session = Depends(get_db)):
    """Xóa file đã lưu và gỡ bỏ khỏi Database stats."""
    # 1. Tìm file trong tất cả domain
    found_path = None
    for domain_dir in settings.storage_dir.iterdir():
        if not domain_dir.is_dir(): continue
        file_path = domain_dir / filename
        if file_path.exists():
            found_path = file_path
            break
            
    if not found_path:
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
        
    # 2. Xóa file và metadata
    try:
        url = "Unknown"
        meta_path = found_path.parent / f"{found_path.name}.meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            url = meta.get("url", "Unknown")
            meta_path.unlink()
        found_path.unlink()
        
        # 3. Xóa khỏi Database stats (nếu có URL)
        if url != "Unknown":
            norm_url = normalize_url(url)
            # Xóa các visit tương ứng với URL này trong tháng này (để stats giảm xuống)
            from models.orm import Visit
            db.query(Visit).filter(Visit.normalized_url == norm_url).delete()
            db.commit()
            
        return {"success": True, "message": f"Đã xóa {filename}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saved")
async def get_saved():
    """Quét và chỉ hiển thị các bản lưu .mhtml."""
    items = []
    
    # Chỉ quét file .mhtml
    for f in settings.storage_dir.glob("**/*.mhtml"):
        if f.name.endswith(".meta.json"): continue
        
        meta_path = f.parent / f"{f.name}.meta.json"
        url, page_type, title = "Unknown", "other", "Unknown"
        
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                url = meta.get("url", "Unknown")
                page_type = meta.get("page_type", "other")
                title = meta.get("title", f.name.split('_202')[0])
            except:
                title = f.name.split('_202')[0]
        else:
            title = f.name.split('_202')[0]
        
        stats = f.stat()
        items.append({
            "filename": f.name,
            "display_name": title,
            "url": url,
            "date": datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size": stats.st_size,
            "page_type": page_type,
            "format": "mhtml",
            "site": f.parent.name
        })
    
    items.sort(key=lambda x: x["date"], reverse=True)
    return items
