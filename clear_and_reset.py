import sys
from pathlib import Path
root = Path("d:/datasets/ruoubia-thuocla-sua/src")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "modules/collector/backend"))

from db.database import SessionLocal
from sqlalchemy import text

def clear_and_reset():
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM products"))
        db.execute(text("UPDATE scraped_files SET status='pending', error_message=NULL"))
        db.commit()
        print("✅ Cleared Products and Reset Scraped Files")
    finally:
        db.close()

if __name__ == "__main__":
    clear_and_reset()
