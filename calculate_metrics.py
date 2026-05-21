
import sys
import os
import csv
from pathlib import Path

# Thêm path
sys.path.append(str(Path(os.getcwd()) / "src"))
sys.path.append(str(Path(os.getcwd()) / "src" / "modules" / "collector" / "backend"))

from db.database import SessionLocal
from sqlalchemy import text

def calculate_full_kpi():
    # 1. Đọc danh sách mục tiêu từ CSV
    csv_path = Path("src/core/urls.csv")
    targets = []
    if csv_path.exists():
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Trích xuất domain từ URL
                url = row.get('URL', '')
                domain = url.replace('https://', '').replace('http://', '').split('/')[0].replace('www.', '')
                if domain:
                    targets.append(domain)
    
    total_targets = len(targets)
    if total_targets == 0:
        total_targets = 52 # Fallback theo file của bạn

    db = SessionLocal()
    try:
        # 2. Kiểm tra Website trong DB
        db_domains = db.execute(text("SELECT domain FROM domains")).fetchall()
        db_domain_list = [row[0].replace('www.', '') for row in db_domains]
        
        # Website có sản phẩm
        prods_per_site = db.execute(text("SELECT source_site, count(*) FROM products GROUP BY source_site")).fetchall()
        sites_with_data = [row[0].replace('www.', '') for row in prods_per_site if row[1] > 0]

        # 3. Tính toán tỷ lệ
        matched_in_db = [t for t in targets if t in db_domain_list]
        success_collected = [t for t in targets if t in sites_with_data]

        web_coverage = (len(matched_in_db) / total_targets) * 100
        collection_rate = (len(success_collected) / total_targets) * 100

        # 4. Thống kê sản phẩm & chất lượng
        total_prods = sum([row[1] for row in prods_per_site])
        dq_avg = db.execute(text("SELECT AVG((raw_data->'dq_report'->>'score')::float) FROM products WHERE raw_data->'dq_report' IS NOT NULL")).scalar() or 0

        print("\n" + "🏁 BÁO CÁO KPI HỆ THỐNG (DỰA TRÊN URLS.CSV)")
        print("="*60)
        print(f"📋 Tổng số mục tiêu (CSV):   {total_targets} website")
        print(f"🌐 Tỷ lệ phủ hệ thống:      {web_coverage:>6.2f}% ({len(matched_in_db)}/{total_targets} web đã nạp)")
        print(f"✅ Tỷ lệ thu thập thành công: {collection_rate:>6.2f}% ({len(success_collected)}/{total_targets} web có dữ liệu)")
        print(f"📦 Tổng sản phẩm thu được:   {total_prods:>7,} SKU")
        print(f"⭐️ Độ chính xác AI (DQ):    {dq_avg*100:>6.2f}%")
        print("="*60)
        
        if len(success_collected) < total_targets:
            missing = [t for t in targets if t not in sites_with_data][:5]
            print(f"⚠️ Các trang chưa có dữ liệu (Top 5): {', '.join(missing)}...")
        
        print("="*60 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    calculate_full_kpi()
