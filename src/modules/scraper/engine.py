"""
Pipeline Engine — điều phối toàn bộ luồng thu thập dữ liệu.
Bronze → Silver → Gold với Gemini AI enhancement.
"""
import asyncio
import uuid
import os
from datetime import datetime
from typing import Optional

from src.core.database import (
    init_db, log_bronze_job, save_silver, save_gold,
    get_conn
)
from src.core.storage import save_bronze
from src.modules.scraper.sites import tiki, bachhoaxanh, winmart
from src.modules.detector.ai_extractor import enhance_product_data

SITES = {
    "tiki": tiki.fetch_products,
    "bachhoaxanh": bachhoaxanh.fetch_products,
    "winmart": winmart.fetch_products,
}

CATEGORIES = ["sua", "ruou-bia", "thuoc-la"]

_run_status: dict = {}


def get_run_status(run_id: str) -> dict:
    return _run_status.get(run_id, {"status": "not_found"})


def list_runs() -> list:
    return list(_run_status.values())


async def run_pipeline(
    sites: list = None,
    categories: list = None,
    use_ai_enhance: bool = True,
    limit_per_site: int = 20,
) -> str:
    init_db()

    run_id = str(uuid.uuid4())[:8]
    selected_sites = sites or list(SITES.keys())
    selected_categories = categories or CATEGORIES
    total = len(selected_sites) * len(selected_categories)

    _run_status[run_id] = {
        "run_id": run_id,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "sites_total": total,
        "sites_done": 0,
        "products_collected": 0,
        "products_extracted": 0,
        "log": [],
        "errors": [],
    }

    def log(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        _run_status[run_id]["log"].append(entry)
        print(entry)

    log(f"Pipeline started | run_id={run_id} | sites={selected_sites} | categories={selected_categories}")

    try:
        for site_name in selected_sites:
            fetcher = SITES.get(site_name)
            if not fetcher:
                log(f"⚠ Unknown site: {site_name}, skipping")
                continue

            for category in selected_categories:
                log(f"▶ Scraping {site_name} / {category}...")
                try:
                    result = await fetcher(category, limit=limit_per_site)
                    products = result.get("products", [])
                    raw_html = result.get("raw", "")

                    html_path = save_bronze(site_name, f"{site_name}/{category}", raw_html)
                    bronze_id = log_bronze_job(
                        site=site_name,
                        url=f"https://{site_name}/{category}",
                        category=category,
                        html_path=html_path,
                        status="done",
                    )
                    log(f"  ✓ Bronze: {len(raw_html)} chars saved → {os.path.basename(html_path)}")

                    if use_ai_enhance and products:
                        log(f"  🧠 Gemini enhancing {len(products)} products...")
                        try:
                            products = await asyncio.to_thread(
                                enhance_product_data, products, site_name, category
                            )
                            log(f"  ✓ AI enhancement done")
                        except Exception as e:
                            log(f"  ⚠ AI enhance failed: {e}")

                    silver_id = save_silver(bronze_id, site_name, category, products)
                    log(f"  ✓ Silver: {len(products)} products → silver_id={silver_id}")

                    save_gold(silver_id, site_name, category, products)
                    log(f"  ✓ Gold: {len(products)} products saved")

                    _run_status[run_id]["products_collected"] += len(products)
                    _run_status[run_id]["products_extracted"] += len(products)

                except Exception as e:
                    err = f"✗ {site_name}/{category}: {e}"
                    log(err)
                    _run_status[run_id]["errors"].append(err)
                    log_bronze_job(site_name, f"https://{site_name}/{category}", category, status="error", error=str(e))

                _run_status[run_id]["sites_done"] += 1

        _run_status[run_id]["status"] = "done"
        _run_status[run_id]["finished_at"] = datetime.now().isoformat()
        log(f"✅ Pipeline finished | total products: {_run_status[run_id]['products_extracted']}")

    except Exception as e:
        _run_status[run_id]["status"] = "error"
        _run_status[run_id]["error"] = str(e)
        _run_status[run_id]["finished_at"] = datetime.now().isoformat()
        log(f"💥 Pipeline error: {e}")

    return run_id
