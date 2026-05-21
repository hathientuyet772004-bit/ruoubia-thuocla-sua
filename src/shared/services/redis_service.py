"""
Redis Service — URL Deduplication cho Collector Tool.
Sử dụng Redis SET để kiểm tra URL đã từng thu thập chưa với O(1).

Key   : "collector:scraped_urls"  (SET chứa url_hash MD5)
Usage :
    from services.redis_service import is_url_seen, mark_url_seen
    if is_url_seen(url_hash):
        return  # skip
    mark_url_seen(url_hash)
"""
import logging
import os

import redis
from redis.exceptions import ConnectionError, TimeoutError

log = logging.getLogger(__name__)

from shared.config import settings

REDIS_HOST     = settings.REDIS_HOST
REDIS_PORT     = settings.REDIS_PORT
REDIS_DB       = 0
REDIS_SET_KEY  = "collector:scraped_urls"

# Connection pool — chia sẻ giữa tất cả request, tránh tạo mới mỗi lần
_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
            max_connections=20,
        )
    return _pool


def get_redis() -> redis.Redis:
    """Trả về Redis client từ connection pool."""
    return redis.Redis(connection_pool=_get_pool())


# ─── Deduplication API ────────────────────────────────────────────────────────

def is_url_seen(url_hash: str) -> bool:
    """
    Kiểm tra url_hash đã có trong Redis SET chưa.
    Trả về False (không chặn) nếu Redis không kết nối được — fail-open.

    Args:
        url_hash: MD5 32 ký tự từ make_url_hash()

    Returns:
        True  → URL đã được thu thập → bỏ qua.
        False → URL mới → cho phép thu thập.
    """
    try:
        return get_redis().sismember(REDIS_SET_KEY, url_hash)
    except (ConnectionError, TimeoutError) as e:
        # Fail-open: nếu Redis không có, vẫn cho scrape (kiểm tra DB bù lại)
        log.warning("⚠️  Redis không kết nối được, fail-open: %s", e)
        return False


def mark_url_seen(url_hash: str) -> None:
    """
    Thêm url_hash vào Redis SET sau khi thu thập thành công.

    Args:
        url_hash: MD5 32 ký tự từ make_url_hash()
    """
    try:
        get_redis().sadd(REDIS_SET_KEY, url_hash)
    except (ConnectionError, TimeoutError) as e:
        log.warning("⚠️  Không thể ghi Redis: %s", e)


def mark_urls_seen_bulk(url_hashes: list[str]) -> None:
    """
    Thêm nhiều hash cùng lúc bằng Redis Pipeline — hiệu quả hơn khi warm-up.

    Args:
        url_hashes: Danh sách MD5 hash.
    """
    if not url_hashes:
        return
    try:
        r = get_redis()
        pipe = r.pipeline(transaction=False)
        for h in url_hashes:
            pipe.sadd(REDIS_SET_KEY, h)
        pipe.execute()
        log.info("✅ Redis bulk add: %d hashes", len(url_hashes))
    except (ConnectionError, TimeoutError) as e:
        log.warning("⚠️  Redis pipeline lỗi: %s", e)


def get_seen_count() -> int:
    """Trả về tổng số URL đã được ghi nhận trong Redis SET."""
    try:
        return get_redis().scard(REDIS_SET_KEY)
    except (ConnectionError, TimeoutError):
        return -1


# ─── Warm-up ──────────────────────────────────────────────────────────────────

def warm_up_from_db() -> int:
    """
    Nạp lại toàn bộ url_hash từ bảng scraped_files trong PostgreSQL vào Redis.
    Gọi một lần duy nhất khi Backend/Worker khởi động để tránh mất dữ liệu
    sau khi Redis restart.

    Returns:
        Số lượng hash đã được nạp vào Redis.
    """
    try:
        # Import ở đây để tránh circular import
        from db.database import SessionLocal
        db = SessionLocal()
        try:
            rows = db.execute(
                "SELECT url_hash FROM scraped_files WHERE url_hash IS NOT NULL"
            ).fetchall()
            hashes = [row[0] for row in rows]
        finally:
            db.close()

        if hashes:
            mark_urls_seen_bulk(hashes)
            log.info("🔥 Redis warm-up: nạp %d url_hash từ Postgres", len(hashes))
        else:
            log.info("🔥 Redis warm-up: không có dữ liệu trong scraped_files")

        return len(hashes)

    except Exception as e:
        log.error("❌ Redis warm-up thất bại: %s", e)
        return 0
