import sys
from pathlib import Path
root = Path("d:/datasets/ruoubia-thuocla-sua/src")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "modules/collector/backend"))

from db.database import SessionLocal
from sqlalchemy import text

def check_file(fid):
    db = SessionLocal()
    try:
        row = db.execute(text(f"SELECT url, minio_path, status, error_message FROM scraped_files WHERE id={fid}")).fetchone()
        if row:
            print(f"ID: {fid}")
            print(f"URL: {row[0]}")
            print(f"Path: {row[1]}")
            print(f"Status: {row[2]}")
            print(f"Error: {row[3]}")
        else:
            print(f"ID {fid} not found.")
    finally:
        db.close()

if __name__ == "__main__":
    check_file(9)
