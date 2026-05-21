
import asyncio
import sys
import os
from pathlib import Path

# Setup paths
sys.path.append(str(Path(os.getcwd()) / "src"))
sys.path.append(str(Path(os.getcwd()) / "src" / "modules" / "collector" / "backend"))

from services.collector_service import collect_domain_monthly

async def main():
    test_domains = [
        {"name": "winemart.vn", "url": "https://winemart.vn"},
        {"name": "kidsplaza.vn", "url": "https://www.kidsplaza.vn"},
        {"name": "thuoclachinhhang.com", "url": "https://thuoclachinhhang.com"}
    ]
    
    print("🚀 Bắt đầu thu thập tự động (Discovery + Collection)...")
    for d in test_domains:
        domain_name = d["name"]
        base_url = d["url"]
        print(f"--- Đang xử lý: {domain_name} ---")
        try:
            # Chạy Discovery (tìm link) và Collect (chụp MHTML)
            # Giới hạn 5 sản phẩm mỗi trang để demo
            result = await collect_domain_monthly(base_url=base_url, max_urls=5)
            print(f"✅ Hoàn tất {domain_name}: Đã tìm thấy {result['discovered']} links, đã nạp {result['queued']} SP.")
        except Exception as e:
            print(f"⚠️ Lỗi {domain_name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
