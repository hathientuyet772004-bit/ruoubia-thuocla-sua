import sys
import json
from pathlib import Path
from collections import Counter

root = Path("d:/datasets/ruoubia-thuocla-sua/src")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "modules/collector/backend"))

from db.database import SessionLocal
from sqlalchemy import text

def generate_dq_report():
    db = SessionLocal()
    try:
        # 1. General Stats
        total_products = db.execute(text("SELECT count(*) FROM products")).scalar()
        print(f"==========================================")
        print(f"📊 DATA QUALITY REPORT (PRELIMINARY)")
        print(f"==========================================")
        print(f"Total Products in Gold Layer: {total_products}")
        
        if total_products == 0:
            print("No data found to analyze.")
            return

        # 2. Source Site Distribution
        source_res = db.execute(text("SELECT source_site, count(*) FROM products GROUP BY source_site ORDER BY count DESC")).fetchall()
        print(f"\n--- 🌐 Source Distribution ---")
        for site, count in source_res:
            pct = (count / total_products) * 100
            print(f"{site or 'Unknown':<20}: {count:>3} ({pct:.1f}%)")

        # 3. Category Distribution
        cat_res = db.execute(text("SELECT category, count(*) FROM products GROUP BY category ORDER BY count DESC")).fetchall()
        print(f"\n--- 🍱 Category Distribution ---")
        for cat, count in cat_res:
            pct = (count / total_products) * 100
            print(f"{cat or 'Uncategorized':<20}: {count:>3} ({pct:.1f}%)")

        # 4. Completeness Metrics
        completeness = {
            "Has Brand": db.execute(text("SELECT count(*) FROM products WHERE brand IS NOT NULL AND brand != 'Unknown'")).scalar(),
            "Has Price": db.execute(text("SELECT count(*) FROM products WHERE price_numeric IS NOT NULL AND price_numeric > 0")).scalar(),
            "Has Image": db.execute(text("SELECT count(*) FROM products WHERE image_url IS NOT NULL")).scalar(),
            "Has Description": db.execute(text("SELECT count(*) FROM products WHERE description IS NOT NULL AND description != ''")).scalar()
        }
        print(f"\n--- 📈 Completeness Metrics ---")
        for metric, count in completeness.items():
            pct = (count / total_products) * 100
            print(f"{metric:<20}: {count:>3} ({pct:.1f}%)")

        # 5. AI DQ Guard Aggregate
        dq_res = db.execute(text("SELECT dq_report FROM products WHERE dq_report IS NOT NULL")).fetchall()
        passed_count = 0
        scores = []
        for row in dq_res:
            try:
                report = row[0]
                if isinstance(report, str):
                    report = json.loads(report)
                if report.get("passed"):
                    passed_count += 1
                scores.append(report.get("score", 0))
            except:
                pass
        
        if scores:
            avg_score = sum(scores) / len(scores)
            print(f"\n--- 🤖 AI Quality Guard (DQ) ---")
            print(f"Passed Guard        : {passed_count} / {len(scores)} ({(passed_count/len(scores)*100):.1f}%)")
            print(f"Average Quality Score: {avg_score:.2f} / 1.0")

        # 6. Sample Data Quality Preview
        print(f"\n--- 🔍 Top 5 High Quality Products ---")
        top_prods = db.execute(text("""
            SELECT name, brand, category, price_numeric, source_site 
            FROM products 
            WHERE brand != 'Unknown' AND price_numeric > 0
            LIMIT 5
        """)).fetchall()
        for p in top_prods:
            print(f"[{p[4]}] {p[1]} | {p[0]} | {p[3]:,.0f} VND ({p[2]})")

    finally:
        db.close()

if __name__ == "__main__":
    generate_dq_report()
