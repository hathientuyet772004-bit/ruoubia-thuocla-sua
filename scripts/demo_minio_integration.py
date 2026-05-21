#!/usr/bin/env python3
"""
Demo script minh họa cách tích hợp MinIO vào flow thu thập dữ liệu

Flow:
1. Scrape dữ liệu từ web
2. Upload dữ liệu thô lên MinIO
3. Download và xử lý dữ liệu từ MinIO
4. Lưu dữ liệu đã xử lý vào PostgreSQL
"""

import json
import time
from datetime import datetime
from scraper.minio_uploader import minio_uploader
from collector.database import SessionLocal
from collector.models_orm import Product

def demo_minio_postgres_integration():
    """Demo tích hợp MinIO + PostgreSQL"""

    print("🚀 Bắt đầu demo MinIO + PostgreSQL integration")

    # 1. Giả lập dữ liệu scrape được
    sample_products = [
        {
            "name": "Bia Tiger 330ml",
            "price": 25000,
            "description": "Bia Tiger lon 330ml, sản xuất tại Việt Nam",
            "url": "https://example.com/tiger",
            "source": "demo"
        },
        {
            "name": "Bia Heineken 330ml",
            "price": 30000,
            "description": "Bia Heineken lon 330ml, nhập khẩu",
            "url": "https://example.com/heineken",
            "source": "demo"
        }
    ]

    # 2. Upload dữ liệu thô lên MinIO
    print("\n📤 Bước 1: Upload dữ liệu thô lên MinIO")
    object_name = minio_uploader.upload_scraped_data(
        sample_products,
        "demo_source",
        "json"
    )

    if not object_name:
        print("❌ Lỗi upload lên MinIO")
        return

    # 3. Download và xử lý dữ liệu từ MinIO
    print("\n📥 Bước 2: Download và xử lý dữ liệu từ MinIO")
    raw_data = minio_uploader.download_and_process_data(object_name)

    if not raw_data:
        print("❌ Lỗi download từ MinIO")
        return

    print(f"✅ Đã download {len(raw_data)} sản phẩm từ MinIO")

    # 4. Lưu vào PostgreSQL
    print("\n💾 Bước 3: Lưu dữ liệu vào PostgreSQL")
    db = SessionLocal()
    try:
        for product_data in raw_data:
            # Kiểm tra sản phẩm đã tồn tại chưa
            existing = db.query(Product).filter_by(
                name=product_data['name'],
                source=product_data['source']
            ).first()

            if existing:
                print(f"⚠️  Sản phẩm đã tồn tại: {product_data['name']}")
                continue

            # Tạo sản phẩm mới
            product = Product(
                name=product_data['name'],
                price=product_data.get('price'),
                description=product_data.get('description'),
                url=product_data.get('url'),
                source=product_data['source']
            )

            db.add(product)
            print(f"✅ Đã thêm sản phẩm: {product.name}")

        db.commit()
        print("✅ Đã lưu tất cả dữ liệu vào PostgreSQL")

    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi lưu vào database: {e}")
    finally:
        db.close()

    # 5. Kiểm tra kết quả
    print("\n🔍 Bước 4: Kiểm tra kết quả")
    db = SessionLocal()
    try:
        products = db.query(Product).filter_by(source="demo").all()
        print(f"📊 Tổng số sản phẩm trong DB: {len(products)}")

        for product in products:
            print(f"  - {product.name}: {product.price} VND")

    except Exception as e:
        print(f"❌ Lỗi truy vấn: {e}")
    finally:
        db.close()

    # 6. Liệt kê files trong MinIO
    print("\n📂 Files trong MinIO:")
    objects = minio_uploader.get_raw_data_list("demo_source", 10)
    for obj in objects:
        print(f"  - {obj}")

    print("\n🎉 Hoàn thành demo!")

def demo_file_upload():
    """Demo upload file lên MinIO"""

    print("\n📤 Demo upload file lên MinIO")

    # Giả lập tạo file CSV
    import pandas as pd

    sample_data = {
        'Tên sản phẩm': ['Bia Tiger', 'Bia Heineken', 'Bia Saigon'],
        'Giá': [25000, 30000, 20000],
        'Nguồn': ['demo', 'demo', 'demo']
    }

    df = pd.DataFrame(sample_data)
    csv_file = 'demo_products.csv'
    df.to_csv(csv_file, index=False)

    # Upload lên MinIO
    object_name = minio_uploader.upload_file(csv_file, 'demo')

    if object_name:
        print(f"✅ Đã upload file CSV lên MinIO: {object_name}")

        # Download lại để kiểm tra
        download_path = 'downloaded_demo.csv'
        if minio_uploader.client.download_file(object_name, download_path):
            print(f"✅ Đã download file về: {download_path}")

    # Dọn dẹp
    import os
    if os.path.exists(csv_file):
        os.remove(csv_file)
    if os.path.exists(download_path):
        os.remove(download_path)

if __name__ == "__main__":
    demo_minio_postgres_integration()
    demo_file_upload()