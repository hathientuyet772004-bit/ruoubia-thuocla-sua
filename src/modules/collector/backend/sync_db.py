import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Setup paths to allow importing from 'src'
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from db.database import SessionLocal, engine
from models.orm import Visit, Base
from shared.services import normalize_url

def sync():
    print("🔄 Đang đồng bộ hóa dữ liệu Filesystem -> Database...")
    db = SessionLocal()
    
    # Đảm bảo bảng tồn tại
    Base.metastore.create_all(bind=engine)
    
    # Path tới data/raw
    storage_dir = root_dir / "store" / "raw"
    print(f"📁 Thư mục lưu trữ: {storage_dir}")
    
    count = 0
    # Quét tất cả file .meta.json của cả .html và .mhtml
    for ext in ["**/*.mhtml.meta.json", "**/*.html.meta.json"]:
        for meta_file in storage_dir.glob(ext):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                url = data.get("url")
                if not url: continue
                
                norm_url = normalize_url(url)
                ts_str = data.get("timestamp")
                if ts_str:
                    try:
                        visited_at = datetime.fromisoformat(ts_str)
                    except:
                        visited_at = datetime.now()
                else:
                    visited_at = datetime.now()
                    
                month_key = f"{visited_at.year}-{visited_at.month:02d}"
                
                # Kiểm tra xem đã có trong DB chưa (dựa trên URL và thời điểm chính xác)
                exists = db.query(Visit).filter(
                    Visit.normalized_url == norm_url,
                    Visit.visited_at == visited_at
                ).first()
                
                if not exists:
                    visit = Visit(
                        normalized_url=norm_url,
                        original_url=url,
                        user_id=data.get("tags", ["system"])[0] if data.get("tags") else "legacy",
                        visited_at=visited_at,
                        load_time_ms=500,
                        page_type=data.get("page_type", "other"),
                        month_key=month_key
                    )
                    db.add(visit)
                    count += 1
                    if count % 10 == 0:
                        db.commit()
                        print(f"✅ Đã đồng bộ {count} mục...")
            except Exception as e:
                print(f"⚠️ Lỗi khi xử lý {meta_file}: {e}")
            
    db.commit()
    db.close()
    print(f"🏁 Hoàn tất! Đã thêm mới {count} bản ghi vào Database.")

if __name__ == "__main__":
    sync()
