import os
from minio import Minio
from minio.error import S3Error

class MinIOClient:
    def __init__(self):
        self.endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        self.access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
        self.secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
        self.bucket_name = os.getenv('MINIO_BUCKET_NAME', 'collector-data')
        self.secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

        # Tạo bucket nếu chưa tồn tại
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Tạo bucket nếu chưa tồn tại"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"✅ Đã tạo bucket: {self.bucket_name}")
        except S3Error as e:
            print(f"❌ Lỗi tạo bucket: {e}")

    def upload_file(self, file_path, object_name):
        """Upload file lên MinIO"""
        try:
            self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path
            )
            print(f"✅ Đã upload {file_path} lên MinIO: {object_name}")
            return True
        except S3Error as e:
            print(f"❌ Lỗi upload file: {e}")
            return False

    def upload_data(self, data, object_name, content_type='application/json'):
        """Upload dữ liệu string/bytes lên MinIO"""
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')

            self.client.put_object(
                self.bucket_name,
                object_name,
                data=data,
                length=len(data),
                content_type=content_type
            )
            print(f"✅ Đã upload dữ liệu lên MinIO: {object_name}")
            return True
        except S3Error as e:
            print(f"❌ Lỗi upload dữ liệu: {e}")
            return False

    def download_file(self, object_name, file_path):
        """Download file từ MinIO"""
        try:
            self.client.fget_object(
                self.bucket_name,
                object_name,
                file_path
            )
            print(f"✅ Đã download {object_name} xuống {file_path}")
            return True
        except S3Error as e:
            print(f"❌ Lỗi download file: {e}")
            return False

    def get_object_data(self, object_name):
        """Lấy dữ liệu từ MinIO object"""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data.decode('utf-8') if isinstance(data, bytes) else data
        except S3Error as e:
            print(f"❌ Lỗi đọc object: {e}")
            return None

    def list_objects(self, prefix=""):
        """Liệt kê objects trong bucket"""
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"❌ Lỗi list objects: {e}")
            return []

    def delete_object(self, object_name):
        """Xóa object khỏi MinIO"""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            print(f"✅ Đã xóa object: {object_name}")
            return True
        except S3Error as e:
            print(f"❌ Lỗi xóa object: {e}")
            return False

# Instance toàn cục
minio_client = MinIOClient()