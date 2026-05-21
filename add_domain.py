import sys
from pathlib import Path
root = Path("d:/datasets/ruoubia-thuocla-sua/src")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "modules/collector/backend"))

from db.database import SessionLocal
from sqlalchemy import text

def add_domain():
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO domains (domain, base_url, enabled, cadence) 
            VALUES ('kidsplaza.vn', 'https://www.kidsplaza.vn', true, 'monthly') 
            ON CONFLICT (domain) DO UPDATE SET enabled = true
        """))
        db.commit()
        print("✅ Added kidsplaza.vn")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    add_domain()
