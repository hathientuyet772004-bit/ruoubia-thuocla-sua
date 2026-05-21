import sys
from pathlib import Path
root = Path("d:/datasets/ruoubia-thuocla-sua/src")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "modules/collector/backend"))

from db.database import SessionLocal
from sqlalchemy import text

def reset_and_run():
    db = SessionLocal()
    try:
        db.execute(text("UPDATE scraped_files SET status='pending'"))
        db.commit()
        print("✅ Reset all files to pending")
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_run()
