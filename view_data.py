
import sys
import os
import json
from pathlib import Path

# Setup paths
sys.path.append(str(Path(os.getcwd()) / "src"))
sys.path.append(str(Path(os.getcwd()) / "src" / "modules" / "collector" / "backend"))

from db.database import SessionLocal
from sqlalchemy import text

def view_sample_data():
    db = SessionLocal()
    try:
        prods = db.execute(text("SELECT name, brand, category, price_numeric, source_site, raw_data FROM products LIMIT 5")).fetchall()

        print("\n" + "="*80)
        print(f"🔍 KIỂM TRA DỮ LIỆU ĐÃ TRÍCH XUẤT (Top {len(prods)})")
        print("="*80)

        for p in prods:
            name, brand, cat, price, source, raw = p
            print(f"📦 Tên SP:      {name}")
            print(f"🏷️ Thương hiệu: {brand or 'N/A'}")
            print(f"🗂️ Danh mục:    {cat or 'N/A'}")
            print(f"💰 Giá:        {price:,.0f} VND" if price else "💰 Giá:        Liên hệ")
            print(f"🌐 Nguồn:       {source}")
            
            # Enrichment data
            details = raw.get('details', {})
            if details:
                print(f"💎 Chi tiết AI: {json.dumps(details, ensure_ascii=False)}")
            
            # DQ Report
            dq = raw.get('dq_report', {})
            if dq:
                status = "✅ PASSED" if dq.get('passed') else "⚠️ WARNING"
                print(f"🛡️ Kiểm định:   {status} (Score: {dq.get('score')})")
            
            print("-" * 80)
    finally:
        db.close()

if __name__ == "__main__":
    view_sample_data()
