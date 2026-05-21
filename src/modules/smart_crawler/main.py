"""
Smart Crawler CLI — Entry point để chạy hệ thống.

Cách dùng:
  python -m smart_crawler.main --url https://ruoutot.net/
  python -m smart_crawler.main --mhtml path/to/file.mhtml --url https://web-bi-chan.com
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

# Thêm current dir vào path để import được smart_crawler
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from smart_crawler.pipeline import AdaptiveCrawler
from smart_crawler.db_manager import DatabaseManager

def init_db():
    """Khởi tạo database schema nếu chưa có."""
    db = DatabaseManager()
    schema_path = Path(__file__).parent / "db" / "schema.sql"
    if schema_path.exists():
        print("🔧 Khởi tạo Database Schema...")
        try:
            sql = schema_path.read_text(encoding="utf-8")
            with db._get_conn().cursor() as cur:
                cur.execute(sql)
            print("✅ Database sẵn sàng.")
        except Exception as e:
            print(f"❌ Lỗi khởi tạo DB: {e}")
    db.close()

def main():
    parser = argparse.ArgumentParser(description="Smart Crawler — Adaptive AI-powered crawling system")
    parser.add_argument("--url", help="URL cần crawl")
    parser.add_argument("--mhtml", help="Đường dẫn tới file .mhtml (nếu dùng strategy MHTML)")
    parser.add_argument("--max-pages", type=int, default=2, help="Số trang listing tối đa")
    parser.add_argument("--force", action="store_true", help="Bắt buộc phân tích lại domain")
    parser.add_argument("--init-db", action="store_true", help="Chạy script khởi tạo database")

    args = parser.parse_args()

    if args.init_db:
        init_db()
        return

    if not args.url and not args.mhtml:
        parser.print_help()
        return

    crawler = AdaptiveCrawler()

    try:
        if args.mhtml:
            if not args.url:
                print("❌ Cần cung cấp --url để xác định domain cho file MHTML.")
                return
            print(f"📂 Đang xử lý file MHTML: {args.mhtml}")
            crawler.process_mhtml(args.mhtml, args.url)
        else:
            print(f"🌐 Đang bắt đầu crawl: {args.url}")
            crawler.run(args.url, max_pages=args.max_pages, force_analyze=args.force)
    
    except KeyboardInterrupt:
        print("\n🛑 Đã dừng theo yêu cầu người dùng.")
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        crawler.close()

if __name__ == "__main__":
    main()
