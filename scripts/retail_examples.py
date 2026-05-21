"""
Script chạy demo crawl BachhoaXANH/WinMart/Lotte dùng Headless strategy.
"""
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from smart_crawler.pipeline import AdaptiveCrawler

def main():
    crawler = AdaptiveCrawler()
    
    # Danh sách các trang retail cần test
    test_urls = [
        "https://www.bachhoaxanh.com/nuoc-ngot",
        # "https://winmart.vn/category/do-uong--c6",
        # "https://lottemart.vn/category/do-uong.html"
    ]
    
    for url in test_urls:
        print(f"\n🚀 Đang test crawl: {url}")
        try:
            # Chạy pipeline - Hệ thống sẽ tự phát hiện JS-required và dùng HeadlessCrawler
            result = crawler.run(url, max_pages=1, force_analyze=False)
            
            if result.get("status") == "success":
                print(f"✅ Thành công! Tìm thấy {result.get('total_products')} sản phẩm.")
            else:
                print(f"❌ Thất bại: {result.get('status')}")
                
        except Exception as e:
            print(f"❌ Lỗi khi chạy demo {url}: {e}")

    crawler.close()

if __name__ == "__main__":
    main()
