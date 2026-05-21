import os
from collector.minio_client import minio_client
from dotenv import load_dotenv

# Load môi trường
load_dotenv()

def check_minio_storage():
    print("🔍 Đang kết nối tới MinIO để kiểm tra dữ liệu...")
    
    # Bucket name từ env hoặc mặc định
    bucket = os.getenv('MINIO_BUCKET_NAME', 'collector-data')
    
    try:
        # Liệt kê tất cả các object
        objects = minio_client.list_objects()
        
        if not objects:
            print(f"🔹 Bucket '{bucket}' hiện đang TRỐNG.")
        else:
            print(f"✅ Tìm thấy {len(objects)} đối tượng trong bucket '{bucket}':")
            print("-" * 50)
            for obj in objects:
                print(f"  - {obj}")
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Không thể kết nối tới MinIO: {e}")
        print("Mẹo: Đảm bảo Docker container của MinIO đang chạy và port 9000 được map chính xác.")

if __name__ == "__main__":
    check_minio_storage()
