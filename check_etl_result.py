import sys
from pathlib import Path
root = Path("d:/datasets/ruoubia-thuocla-sua/src")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "modules/collector/backend"))

from db.database import SessionLocal
from sqlalchemy import text

def check_db():
    db = SessionLocal()
    try:
        # Check Scraped Files
        res = db.execute(text("SELECT status, count(*) FROM scraped_files GROUP BY status")).fetchall()
        print("--- SCRAPED FILES STATUS ---")
        for r in res:
            print(f"{r[0]}: {r[1]}")
        
        # Check Products
        res_prod = db.execute(text("SELECT count(*) FROM products")).scalar()
        print(f"\nTOTAL PRODUCTS IN DB: {res_prod}")
        
        if res_prod > 0:
            print("\n--- NEWEST 5 PRODUCTS ---")
            prods = db.execute(text("SELECT name, price_numeric, source_site, updated_at FROM products ORDER BY updated_at DESC LIMIT 5")).fetchall()
            for p in prods:
                print(f"Name: {p[0]} | Price: {p[1]} | Site: {p[2]} | At: {p[3]}")
                
        # Check for errors in failed files
        failed = db.execute(text("SELECT id, url, error_message FROM scraped_files WHERE status='failed' LIMIT 3")).fetchall()
        if failed:
            print("\n--- SAMPLE ERRORS ---")
            for f in failed:
                print(f"ID: {f[0]} | URL: {f[1]}\nError: {f[2]}\n")

    finally:
        db.close()

if __name__ == "__main__":
    check_db()
