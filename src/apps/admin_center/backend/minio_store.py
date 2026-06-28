"""MinIO object storage — optional overlay for MHTML files.

Falls back silently to local filesystem if MINIO_ENDPOINT is not set.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Any

log = logging.getLogger("admin_center.minio_store")


class MinioStore:
    """Wraps the MinIO Python client with a local-filesystem fallback."""

    def __init__(self) -> None:
        self._client: Any = None
        self._bucket: str = ""
        self._ready: bool = False
        self._init_attempted: bool = False

    def _ensure_init(self) -> bool:
        if self._init_attempted:
            return self._ready
        self._init_attempted = True
        endpoint = os.environ.get("MINIO_ENDPOINT", "")
        access_key = os.environ.get("MINIO_ACCESS_KEY", "")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "")
        bucket = os.environ.get("MINIO_BUCKET", "admin-center-raw")
        if not endpoint or not access_key or not secret_key:
            log.info("MinIO not configured (MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY unset); using local filesystem.")
            self._ready = False
            return False
        try:
            from minio import Minio
            secure = not endpoint.startswith("http://")
            clean_endpoint = endpoint.replace("http://", "").replace("https://", "").rstrip("/")
            client = Minio(clean_endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
                log.info("MinIO: created bucket %s", bucket)
            self._client = client
            self._bucket = bucket
            self._ready = True
            log.info("MinIO store ready — endpoint=%s bucket=%s", endpoint, bucket)
            return True
        except Exception as exc:
            log.warning("MinIO init failed: %s — falling back to local filesystem.", exc)
            self._ready = False
            return False

    def upload(self, key: str, data: bytes) -> str | None:
        """Upload bytes to MinIO. Returns the object key on success, None otherwise."""
        if not self._ensure_init():
            return None
        try:
            self._client.put_object(
                self._bucket, key,
                io.BytesIO(data), length=len(data),
                content_type="application/octet-stream",
            )
            return key
        except Exception as exc:
            log.warning("MinIO upload failed for %s: %s", key, exc)
            return None

    def download(self, key: str) -> bytes | None:
        """Download bytes from MinIO. Returns None if not available."""
        if not self._ensure_init():
            return None
        try:
            response = self._client.get_object(self._bucket, key)
            return response.read()
        except Exception as exc:
            log.warning("MinIO download failed for %s: %s", key, exc)
            return None

    def delete(self, key: str) -> bool:
        """Delete an object from MinIO."""
        if not self._ensure_init():
            return False
        try:
            self._client.remove_object(self._bucket, key)
            return True
        except Exception as exc:
            log.warning("MinIO delete failed for %s: %s", key, exc)
            return False

    @property
    def is_configured(self) -> bool:
        return self._ensure_init()


minio_store = MinioStore()
