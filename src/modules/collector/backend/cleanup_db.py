import os
import sys
import json
from pathlib import Path

# Setup paths to allow importing from 'src'
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from db.database import SessionLocal
from models.orm import Visit
from shared.config import settings
from shared.services import normalize_url, get_domain

def cleanup():
    print("🧹 Đang dọn dẹp Database (Xóa các bản ghi không còn file trên ổ cứng)...")
    db = SessionLocal()
    
    # Lấy tất cả visits
    visits = db.query(Visit).all()
    
    deleted_count = 0
    total = len(visits)
    
    for i, v in enumerate(visits):
        domain = get_domain(v.original_url)
        site_dir = settings.storage_dir / domain
        
        # Nếu thư mục domain không tồn tại -> Chắc chắn đã xóa
        if not site_dir.exists():
            db.delete(v)
            deleted_count += 1
            continue
            
        # Nếu thư mục tồn tại, kiểm tra xem có file nào chứa URL này không
        found = False
        norm_url = v.normalized_url
        
        for meta_file in site_dir.glob("*.meta.json"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if normalize_url(meta.get("url", "")) == norm_url:
                    found = True
                    break
            except: continue
            
        if not found:
            db.delete(v)
            deleted_count += 1
            
        if (i + 1) % 50 == 0:
            print(f"⌛ Đã kiểm tra {i+1}/{total} mục...")

    db.commit()
    db.close()
    print(f"🏁 Hoàn tất! Đã dọn dẹp {deleted_count} bản ghi 'ma' khỏi Database.")

if __name__ == "__main__":
    cleanup()
