import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

# Đảm bảo Airflow có thể import các modules từ thư mục src
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
    sys.path.append(f"{PROJECT_ROOT}/src")

try:
    from modules.collector_strategies.api.tiki_collector import TikiCollector
    from modules.collector_strategies.api.coop_collector import CoopCollector
except Exception as e:
    TikiCollector = None  # type: ignore[assignment]
    CoopCollector = None  # type: ignore[assignment]
    log.warning("daily_ecom_sync: không import được collectors (bỏ qua DAG): %s", e)

DatabaseManager = None
try:
    # Legacy module (repo hiện tại có thể không còn)
    from smart_crawler.db_manager import DatabaseManager  # type: ignore
except Exception as e:
    log.warning("daily_ecom_sync: không import được smart_crawler (bỏ qua DAG): %s", e)

default_args = {
    'owner': 'antigravity',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def sync_tiki_products():
    """Nhiệm vụ đồng bộ dữ liệu từ Tiki API."""
    if TikiCollector is None or DatabaseManager is None:
        raise RuntimeError("daily_ecom_sync is disabled (missing collectors or DatabaseManager)")

    collector = TikiCollector()
    db = DatabaseManager()
    
    # Danh mục Sữa & Đồ uống
    categories = [
        {"id": 2551, "name": "Sữa - Đồ uống"},
        {"id": 1111, "name": "Bia - Rượu"}
    ]
    
    total_saved = 0
    for cat in categories:
        url = f"https://tiki.vn/api/v2/products?limit=50&category={cat['id']}"
        products = collector.collect(url)
        if products:
            # Gán thêm category metadata nếu cần
            count = db.save_products(products)
            total_saved += count
            
    db.close()
    print(f"✅ Hoàn thành Tiki: Đã cập nhật {total_saved} sản phẩm.")

def sync_coop_products():
    """Nhiệm vụ đồng bộ dữ liệu từ Co.op Online API."""
    if CoopCollector is None or DatabaseManager is None:
        raise RuntimeError("daily_ecom_sync is disabled (missing collectors or DatabaseManager)")

    collector = CoopCollector()
    db = DatabaseManager()

    slugs = ["/c/sua-san-pham-tu-sua", "/c/thuc-uong-nuoc-giai-khat"]
    
    total_saved = 0
    for slug in slugs:
        products = collector.collect_category(slug)
        if products:
            count = db.save_products(products)
            total_saved += count
            
    db.close()
    print(f"✅ Hoàn thành Co.op: Đã cập nhật {total_saved} sản phẩm.")

if TikiCollector is not None and CoopCollector is not None and DatabaseManager is not None:
    with DAG(
        'daily_ecom_sync_gold',
        default_args=default_args,
        description='Đồng bộ dữ liệu Rượu bia - Sữa hàng ngày từ API (Gold Layer)',
        schedule_interval='0 2 * * *', # 2:00 AM hàng ngày
        start_date=datetime(2025, 1, 1),
        catchup=False,
        tags=['collector', 'api', 'gold'],
    ) as dag:

        task_tiki = PythonOperator(
            task_id='sync_tiki_api',
            python_callable=sync_tiki_products,
        )

        task_coop = PythonOperator(
            task_id='sync_coop_api',
            python_callable=sync_coop_products,
        )

        task_tiki >> task_coop
