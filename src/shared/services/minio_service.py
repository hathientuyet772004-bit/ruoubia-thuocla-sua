"""
MinIO Service — Upload/Download MHTML và processed JSON.
Sử dụng trong: backend (lưu file khi save-mhtml) và etl_worker (đọc để xử lý).
"""
import hashlib
import io
import json
import logging
import os
from datetime import date, datetime

from minio import Minio
from minio.error import S3Error

log = logging.getLogger(__name__)

from shared.config import settings

BUCKET    = settings.MINIO_BUCKET_NAME
ENDPOINT  = settings.MINIO_ENDPOINT
ACCESS    = settings.MINIO_ACCESS_KEY
SECRET    = settings.MINIO_SECRET_KEY
SECURE    = settings.MINIO_SECURE

_client: Minio | None = None


# ─── Client singleton ─────────────────────────────────────────────────────────

def get_client() -> Minio:
    """Trả về MinIO client (singleton), tự tạo bucket nếu chưa có."""
    global _client
    if _client is None:
        _client = Minio(ENDPOINT, access_key=ACCESS, secret_key=SECRET, secure=SECURE)
        _ensure_bucket(_client)
    return _client


def _ensure_bucket(client: Minio) -> None:
    try:
        if not client.bucket_exists(BUCKET):
            client.make_bucket(BUCKET)
            log.info("✅ Đã tạo MinIO bucket: %s", BUCKET)
    except S3Error as e:
        log.error("❌ Không thể tạo bucket: %s", e)
        raise


# ─── URL Hashing ──────────────────────────────────────────────────────────────

def make_url_hash(url: str) -> str:
    """
    Chuẩn hóa URL và trả về MD5 hash 32 ký tự.
    Dùng thống nhất cho cả MinIO path, Redis SET và PostgreSQL url_hash.
    """
    # Bỏ protocol, www, trailing slash, query string tracking params
    import re
    normalized = url.strip().lower()
    normalized = re.sub(r"^https?://", "", normalized)
    normalized = re.sub(r"^www\.", "", normalized)
    normalized = normalized.rstrip("/")
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def make_minio_path(url_hash: str, domain: str, folder: str = "raw") -> str:
    """Tạo đường dẫn object chuẩn trong MinIO."""
    today = date.today().isoformat()          # e.g. "2026-04-23"
    return f"{folder}/{domain}/{today}/{url_hash}.mhtml"


# ─── Upload ───────────────────────────────────────────────────────────────────

def upload_mhtml(url: str, content: str, domain: str, page_type: str = "other") -> str:
    """
    Upload file MHTML lên MinIO.

    Returns:
        minio_path: Đường dẫn object để lưu vào bảng scraped_files.

    Raises:
        S3Error: Khi upload thất bại.
    """
    client   = get_client()
    url_hash = make_url_hash(url)
    path     = make_minio_path(url_hash, domain, folder="raw")

    raw_bytes = content.encode("utf-8")
    client.put_object(
        BUCKET,
        path,
        data=io.BytesIO(raw_bytes),
        length=len(raw_bytes),
        content_type="multipart/related",
        metadata={
            "url":        url,
            "url-hash":   url_hash,      # MinIO metadata key không dùng _
            "domain":     domain,
            "scraped-at": datetime.now().isoformat(),
            "page-type":  page_type,
        },
    )
    log.info("📤 MinIO upload OK: %s (%d bytes)", path, len(raw_bytes))
    return path


def upload_processed_json(url_hash: str, domain: str, data: dict) -> str:
    """
    Lưu kết quả trích xuất (đã xử lý) vào thư mục processed/.
    Dùng sau khi ETL worker xử lý xong một file.

    Returns:
        minio_path: e.g. "processed/winemart.vn/2026-04-23/{hash}.json"
    """
    client = get_client()
    today  = date.today().isoformat()
    path   = f"processed/{domain}/{today}/{url_hash}.json"

    raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        BUCKET, path,
        data=io.BytesIO(raw),
        length=len(raw),
        content_type="application/json",
    )
    log.info("💾 MinIO processed upload: %s", path)
    return path


# ─── Download ─────────────────────────────────────────────────────────────────

def download_mhtml(minio_path: str) -> str:
    """
    Download file MHTML từ MinIO.

    Returns:
        Nội dung trang dưới dạng string UTF-8.

    Raises:
        S3Error: Khi object không tồn tại hoặc kết nối lỗi.
    """
    client = get_client()
    resp   = client.get_object(BUCKET, minio_path)
    try:
        content = resp.read()
        return content.decode("utf-8", errors="replace")
    finally:
        resp.close()
        resp.release_conn()


# ─── Listing ──────────────────────────────────────────────────────────────────

def list_raw_objects(domain: str | None = None, limit: int = 200) -> list[str]:
    """Liệt kê các object trong thư mục raw/, có thể lọc theo domain."""
    client = get_client()
    prefix = f"raw/{domain}/" if domain else "raw/"
    try:
        objs = [o.object_name for o in client.list_objects(BUCKET, prefix=prefix, recursive=True)]
        return objs[:limit]
    except S3Error as e:
        log.error("❌ Lỗi list objects: %s", e)
        return []


def get_presigned_url(minio_path: str, expires_hours: int = 1) -> str | None:
    """
    Tạo URL có chữ ký tạm thời để Frontend download trực tiếp từ MinIO.
    Không cần đi qua Backend → giảm tải đáng kể.
    """
    from datetime import timedelta
    client = get_client()
    try:
        return client.presigned_get_object(BUCKET, minio_path,
                                           expires=timedelta(hours=expires_hours))
    except S3Error as e:
        log.error("❌ Presigned URL error: %s", e)
        return None
