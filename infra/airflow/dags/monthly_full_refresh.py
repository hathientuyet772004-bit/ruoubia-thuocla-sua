"""
DAG: monthly_full_refresh
Schedule: 03:10 AM (Asia/Ho_Chi_Minh) on day 1 of each month

Backbone pipeline (skeleton):
  1. health_check      — Ping MinIO + Postgres + Redis
  2. sync_domains      — Upsert domains + cadence from domain_cadence.json
  3. create_monthly_run— Create crawl_runs + crawl_tasks (discover/collect/extract)
  4. discover_plan     — Placeholder (future: sitemap/category discovery)
  5. collect_pages     — Placeholder (future: auto crawl -> MinIO + scraped_files)
  6. extract_load      — Run ETL batch on pending scraped_files
  7. finalize_run      — Mark crawl_runs done/failed
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
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

DEFAULT_ARGS = {
    "owner": "collector",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}


def _load_domain_config() -> list[dict]:
    cfg_path = Path(__file__).with_name("domain_cadence.json")
    if not cfg_path.exists():
        return []
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def task_health_check(**context):
    errors = []

    # 1. MinIO
    try:
        from services.minio_service import get_client
        get_client().list_buckets()
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

    # 3. Redis (non-blocking)
    try:
        from services.redis_service import get_redis
        get_redis().ping()
        log.info("✅ Redis OK")
    except Exception as e:
        log.warning("⚠️  Redis không khả dụng (non-blocking): %s", e)

    if errors:
        raise RuntimeError(f"Health check thất bại: {'; '.join(errors)}")


def task_sync_domains(**context):
    """Upsert domain registry from JSON config."""
    config_rows = _load_domain_config()
    if not config_rows:
        log.warning("Không có domain config (domain_cadence.json trống).")
        return

    from db.database import SessionLocal

    db = SessionLocal()
    try:
        for row in config_rows:
            domain = (row.get("domain") or "").strip().lower()
            base_url = (row.get("base_url") or "").strip()
            if not domain or not base_url:
                continue

            db.execute(
                """
                INSERT INTO domains (domain, base_url, strategy, cadence, enabled, prompt_version, updated_at)
                VALUES (:d, :u, :s, :c, :e, :p, now())
                ON CONFLICT (domain) DO UPDATE
                SET base_url = EXCLUDED.base_url,
                    strategy = EXCLUDED.strategy,
                    cadence  = EXCLUDED.cadence,
                    enabled  = EXCLUDED.enabled,
                    prompt_version = EXCLUDED.prompt_version,
                    updated_at = now()
                """,
                {
                    "d": domain,
                    "u": base_url,
                    "s": (row.get("strategy") or "auto"),
                    "c": (row.get("cadence") or "monthly"),
                    "e": bool(row.get("enabled", True)),
                    "p": (row.get("prompt_version") or None),
                },
            )
        db.commit()
        log.info("✅ Sync domains xong: %d rows", len(config_rows))
    finally:
        db.close()


def task_create_monthly_run(**context):
    """Create crawl_runs + tasks for enabled monthly domains."""
    ds = context["ds"]  # YYYY-MM-DD
    run_key = f"monthly_{ds[:7].replace('-', '')}"
    from db.database import SessionLocal

    db = SessionLocal()
    try:
        run_id = db.execute(
            """
            INSERT INTO crawl_runs (run_key, cadence, status, meta)
            VALUES (:k, 'monthly', 'running', CAST(:m AS jsonb))
            ON CONFLICT (run_key) DO UPDATE
            SET status='running', started_at=now()
            RETURNING id
            """,
            {
                "k": run_key,
                "m": json.dumps({"scheduled_for": ds, "uuid": str(uuid.uuid4())}),
            },
        ).scalar()

        domains = db.execute(
            """
            SELECT id, domain, base_url
            FROM domains
            WHERE enabled = true AND cadence = 'monthly'
            ORDER BY domain ASC
            """
        ).fetchall()

        created = 0
        for d_id, domain, base_url in domains:
            # discover
            db.execute(
                """
                INSERT INTO crawl_tasks (run_id, domain_id, task_type, target_url, status, meta)
                VALUES (:r, :d, 'discover', :u, 'pending', :m::jsonb)
                """,
                {"r": run_id, "d": d_id, "u": base_url, "m": json.dumps({"domain": domain})},
            )
            # collect (placeholder)
            db.execute(
                """
                INSERT INTO crawl_tasks (run_id, domain_id, task_type, target_url, status)
                VALUES (:r, :d, 'collect', :u, 'pending')
                """,
                {"r": run_id, "d": d_id, "u": base_url},
            )
            # extract (runs ETL over scraped_files)
            db.execute(
                """
                INSERT INTO crawl_tasks (run_id, domain_id, task_type, target_url, status)
                VALUES (:r, :d, 'extract', :u, 'pending')
                """,
                {"r": run_id, "d": d_id, "u": base_url},
            )
            created += 3

        db.commit()
        context["ti"].xcom_push(key="run_key", value=run_key)
        context["ti"].xcom_push(key="run_id", value=run_id)
        context["ti"].xcom_push(key="tasks_created", value=created)
        log.info("✅ Created run=%s tasks=%d domains=%d", run_key, created, len(domains))
    finally:
        db.close()


def task_discover_plan(**context):
    """
    Placeholder for discovery.
    Future: sitemap/category discovery -> enqueue crawl targets.
    """
    run_id = context["ti"].xcom_pull(task_ids="create_monthly_run", key="run_id")
    if not run_id:
        return
    log.info("🔎 Discover placeholder for run_id=%s (no-op)", run_id)


def task_collect_pages(**context):
    """
    Call backend collector API to perform monthly collection:
      POST http://backend:8080/api/collect/monthly
    """
    run_id = context["ti"].xcom_pull(task_ids="create_monthly_run", key="run_id")
    if not run_id:
        return

    backend_url = os.getenv("COLLECTOR_BACKEND_URL", "http://backend:8080")
    max_urls = int(os.getenv("COLLECT_MAX_URLS_PER_DOMAIN", "0"))
    payload = {}
    if max_urls > 0:
        payload["max_urls_per_domain"] = max_urls

    import requests

    log.info("🕷️  Calling backend collect API: %s", backend_url)
    resp = requests.post(
        f"{backend_url}/api/collect/monthly",
        json=payload,
        timeout=int(os.getenv("COLLECT_API_TIMEOUT_SEC", "3600")),
    )
    resp.raise_for_status()
    data = resp.json()
    context["ti"].xcom_push(key="collect_result", value=data)
    log.info("✅ Collect done: %s", data.get("totals"))


def task_extract_load(**context):
    """
    Run ETL batch to process scraped_files pending.
    This is the current end-to-end piece that already works with MinIO + Postgres.
    """
    from etl.etl_worker import run_etl_batch
    result = run_etl_batch()
    context["ti"].xcom_push(key="etl_result", value=result)

    log.info(
        "ETL result: run_id=%s total=%d ok=%d failed=%d duration=%.2fs",
        result["run_id"], result["total"], result["ok"], result["failed"], result["duration_sec"]
    )


def task_finalize_run(**context):
    run_id = context["ti"].xcom_pull(task_ids="create_monthly_run", key="run_id")
    run_key = context["ti"].xcom_pull(task_ids="create_monthly_run", key="run_key")
    etl_result = context["ti"].xcom_pull(task_ids="extract_load", key="etl_result") or {}
    if not run_id:
        return

    status = "done"
    if etl_result.get("total", 0) > 0 and etl_result.get("failed", 0) / max(etl_result.get("total", 1), 1) > 0.5:
        status = "failed"

    from db.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(
            """
            UPDATE crawl_runs
            SET status=:s, finished_at=now(),
                meta = COALESCE(meta, '{}'::jsonb) || CAST(:m AS jsonb)
            WHERE id=:i
            """,
            {
                "s": status,
                "i": run_id,
                "m": json.dumps({"etl": etl_result, "run_key": run_key, "finalized_at": datetime.now().isoformat()}),
            },
        )
        db.commit()
        log.info("🏁 Finalized run=%s status=%s", run_key, status)
    finally:
        db.close()


with DAG(
    dag_id="monthly_full_refresh",
    description="Monthly backbone: discover→collect→extract (skeleton)",
    default_args=DEFAULT_ARGS,
    schedule_interval="10 3 1 * *",   # 03:10 AM ngày 1 mỗi tháng
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["collector", "monthly", "orchestration"],
) as dag:

    health_check = PythonOperator(
        task_id="health_check",
        python_callable=task_health_check,
    )

    sync_domains = PythonOperator(
        task_id="sync_domains",
        python_callable=task_sync_domains,
    )

    create_monthly_run = PythonOperator(
        task_id="create_monthly_run",
        python_callable=task_create_monthly_run,
    )

    discover_plan = PythonOperator(
        task_id="discover_plan",
        python_callable=task_discover_plan,
    )

    collect_pages = PythonOperator(
        task_id="collect_pages",
        python_callable=task_collect_pages,
    )

    extract_load = PythonOperator(
        task_id="extract_load",
        python_callable=task_extract_load,
        execution_timeout=timedelta(hours=6),
    )

    finalize_run = PythonOperator(
        task_id="finalize_run",
        python_callable=task_finalize_run,
        trigger_rule="all_done",
    )

    health_check >> sync_domains >> create_monthly_run >> discover_plan >> collect_pages >> extract_load >> finalize_run
