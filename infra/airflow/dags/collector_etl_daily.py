"""
DAG: collector_etl_daily
Lịch chạy: 02:00 AM (Asia/Ho_Chi_Minh) mỗi ngày

Pipeline:
  1. health_check      — Ping MinIO + Postgres + Redis
  2. redis_warmup      — Nạp lại url_hash từ Postgres vào Redis (nếu Redis khởi động lại)
  3. etl_batch         — Xử lý các file .mhtml pending từ MinIO → Postgres
  4. notify_summary    — Log tóm tắt kết quả lên Airflow XCom
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

log = logging.getLogger(__name__)

# ── Path setup — Airflow container mount /opt/airflow/collector_backend ────────
BACKEND_PATH = Path(os.getenv("COLLECTOR_BACKEND_PATH", "/opt/airflow/collector_backend"))
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

# ── DAG default args ───────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner":            "collector",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}


# ─────────────────────────────────────────────────────────────────────────────
# Task functions
# ─────────────────────────────────────────────────────────────────────────────

def task_health_check(**context):
    """Kiểm tra kết nối MinIO, Postgres, Redis trước khi chạy ETL."""
    errors = []

    # 1. MinIO
    try:
        from services.minio_service import get_client
        client = get_client()
        client.list_buckets()
        log.info("✅ MinIO OK")
    except Exception as e:
        errors.append(f"MinIO: {e}")

    # 2. Postgres
    try:
        from db.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        log.info("✅ Postgres OK")
    except Exception as e:
        errors.append(f"Postgres: {e}")

    # 3. Redis
    try:
        from services.redis_service import get_redis
        get_redis().ping()
        log.info("✅ Redis OK")
    except Exception as e:
        # Redis lỗi không chặn pipeline (fail-open)
        log.warning("⚠️  Redis không khả dụng (non-blocking): %s", e)

    if errors:
        raise RuntimeError(f"Health check thất bại: {'; '.join(errors)}")

    log.info("🟢 Tất cả health checks OK")


def task_redis_warmup(**context):
    """
    Warm-up Redis từ Postgres.
    Chỉ thực sự ghi nếu Redis đang trống (tránh lãng phí khi Redis đã có dữ liệu).
    """
    try:
        from services.redis_service import get_seen_count, warm_up_from_db
        current = get_seen_count()
        log.info("Redis hiện có %d url_hash", current)

        if current <= 0:
            loaded = warm_up_from_db()
            log.info("🔥 Warm-up xong: %d hashes nạp vào Redis", loaded)
            context["ti"].xcom_push(key="warmup_count", value=loaded)
        else:
            log.info("✅ Redis đã có dữ liệu, bỏ qua warm-up")
            context["ti"].xcom_push(key="warmup_count", value=current)
    except Exception as e:
        log.warning("Redis warm-up lỗi (non-blocking): %s", e)


def task_etl_batch(**context):
    """
    Chạy một vòng ETL batch: MinIO pending files → Postgres products/branches.
    Đẩy kết quả vào XCom để task notify sử dụng.
    """
    from etl.etl_worker import run_etl_batch
    result = run_etl_batch()

    log.info(
        "ETL kết quả: run_id=%s total=%d ok=%d failed=%d duration=%.2fs",
        result["run_id"], result["total"], result["ok"],
        result["failed"], result["duration_sec"],
    )

    # Đẩy vào XCom để notify task đọc
    context["ti"].xcom_push(key="etl_result", value=result)

    # Raise nếu có quá nhiều lỗi (> 50%)
    if result["total"] > 0 and result["failed"] / result["total"] > 0.5:
        raise RuntimeError(
            f"Quá nhiều file lỗi: {result['failed']}/{result['total']}"
        )


def task_notify_summary(**context):
    """Log bản tóm tắt kết quả ETL vào Airflow logs và XCom."""
    ti     = context["ti"]
    result = ti.xcom_pull(task_ids="etl_batch", key="etl_result") or {}
    warmup = ti.xcom_pull(task_ids="redis_warmup", key="warmup_count") or 0

    summary = {
        "run_date":      context["ds"],
        "etl_run_id":    result.get("run_id"),
        "files_total":   result.get("total", 0),
        "files_ok":      result.get("ok", 0),
        "files_failed":  result.get("failed", 0),
        "duration_sec":  result.get("duration_sec", 0),
        "redis_warmup":  warmup,
        "completed_at":  datetime.now().isoformat(),
    }

    log.info("─" * 60)
    log.info("📊 ETL DAILY SUMMARY — %s", context["ds"])
    for k, v in summary.items():
        log.info("   %-20s: %s", k, v)
    log.info("─" * 60)

    ti.xcom_push(key="summary", value=summary)


# ─────────────────────────────────────────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────────────────────────────────────────

with DAG(
    dag_id="collector_etl_daily",
    description="Daily ETL: MinIO MHTML → PostgreSQL products & branches",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 2 * * *",          # 02:00 AM mỗi ngày
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,                       # Không chạy song song
    tags=["collector", "etl", "minio", "postgres"],
) as dag:

    health_check = PythonOperator(
        task_id="health_check",
        python_callable=task_health_check,
    )

    redis_warmup = PythonOperator(
        task_id="redis_warmup",
        python_callable=task_redis_warmup,
    )

    etl_batch = PythonOperator(
        task_id="etl_batch",
        python_callable=task_etl_batch,
        execution_timeout=timedelta(hours=2),
    )

    notify_summary = PythonOperator(
        task_id="notify_summary",
        python_callable=task_notify_summary,
        trigger_rule="all_done",             # Chạy dù task trước lỗi
    )

    # ── Thứ tự chạy ────────────────────────────────────────────────
    health_check >> redis_warmup >> etl_batch >> notify_summary
