
import csv
import sys
import os
from pathlib import Path

# Setup paths
sys.path.append(str(Path(os.getcwd()) / "src"))
sys.path.append(str(Path(os.getcwd()) / "src" / "modules" / "collector" / "backend"))

from db.database import SessionLocal
from sqlalchemy import text

def bootstrap_domains():
    csv_path = Path("src/core/urls.csv")
    if not csv_path.exists():
        print("❌ Không tìm thấy file urls.csv")
        return

    db = SessionLocal()
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('Tên Website')
                url = row.get('URL')
                if not url: continue
                
                domain = url.replace('https://', '').replace('http://', '').split('/')[0].replace('www.', '')
                
                # Upsert vào bảng domains
                db.execute(text("""
                    INSERT INTO domains (domain, base_url, strategy, cadence, enabled)
                    VALUES (:d, :u, 'auto', 'monthly', true)
                    ON CONFLICT (domain) DO UPDATE SET 
                        enabled = true,
                        base_url = EXCLUDED.base_url
                """), {'d': domain, 'u': url})
                count += 1
        
        db.commit()
        print(f"✅ Đã nạp thành công {count} mục tiêu từ CSV vào Database.")
    except Exception as e:
        print(f"❌ Lỗi đồng bộ: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    bootstrap_domains()
