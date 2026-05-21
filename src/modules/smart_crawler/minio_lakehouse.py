"""
MinIOLakehouse — Giao tiếp với MinIO Object Storage theo cấu trúc Lakehouse.
Cấu trúc: /data/{category}/{domain}/*.html
"""
from __future__ import annotations

import os
import logging
from typing import List, Optional
from minio import Minio
from minio.error import S3Error

from shared.config import settings

logger = logging.getLogger("smart_crawler.minio_lakehouse")

class MinIOLakehouse:
    """Quản lý duyệt và tải file từ Lakehouse trên MinIO."""

    def __init__(self):
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.bucket = settings.MINIO_BUCKET_NAME
        self.secure = settings.MINIO_SECURE

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        self.base_prefix = "data/"

    def list_categories(self) -> List[str]:
        """Liệt kê các categories (thư mục con của /data/)."""
        try:
            objects = self.client.list_objects(self.bucket, prefix=self.base_prefix, recursive=False)
            categories = []
            for obj in objects:
                if obj.is_dir:
                    # Lấy tên thư mục cuối cùng
                    name = obj.object_name.rstrip('/').split('/')[-1]
                    if name:
                        categories.append(name)
            return categories
        except S3Error as e:
            logger.error(f"MinIO S3Error list_categories: {e}")
            return []

    def list_domains(self, category: str) -> List[str]:
        """Liệt kê các domains thuộc một category."""
        prefix = f"{self.base_prefix}{category}/"
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=False)
            domains = []
            for obj in objects:
                if obj.is_dir:
                    name = obj.object_name.rstrip('/').split('/')[-1]
                    if name:
                        domains.append(name)
            return domains
        except S3Error as e:
            logger.error(f"MinIO S3Error list_domains: {e}")
            return []

    def list_files(self, category: str, domain: str) -> List[str]:
        """Liệt kê các file .html trong /data/{category}/{domain}/."""
        prefix = f"{self.base_prefix}{category}/{domain}/"
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
            files = []
            for obj in objects:
                if not obj.is_dir and (obj.object_name.endswith('.html') or obj.object_name.endswith('.mhtml')):
                    files.append(obj.object_name)
            return files
        except S3Error as e:
            logger.error(f"MinIO S3Error list_files: {e}")
            return []

    def get_file_content(self, object_name: str) -> Optional[str]:
        """Tải và decode nội dung file từ MinIO."""
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            
            # Tự động decode
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                import chardet
                res = chardet.detect(data)
                return data.decode(res['encoding'] or 'latin-1', errors='ignore')
                
        except S3Error as e:
            logger.error(f"MinIO S3Error get_file_content: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load file from MinIO: {e}")
            return None
