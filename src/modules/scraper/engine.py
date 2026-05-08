"""
Pipeline Engine — điều phối Bronze → Silver → Gold với Gemini AI.
"""
import asyncio
import os
import uuid
from typing import Optional

from src.core.database import insert_bronze_job, insert_silver, insert_gold_batch
from src.core.logging import logger
from src.core.storage import save_bronze
from src.models.pipeline import PipelineRun, PipelineStatus
from src.models.product import ScrapeResult
from src.modules.detector.ai_extractor import enhance_products
from src.modules.scraper.base import BaseScraper
from src.modules.scraper.sites.bachhoaxanh import BachHoaXanhScraper
from src.modules.scraper.sites.tiki import TikiScraper
from src.modules.scraper.sites.winmart import WinMartScraper

SCRAPERS: dict[str, BaseScraper] = {
    "tiki":         TikiScraper(),
    "bachhoaxanh":  BachHoaXanhScraper(),
    "winmart":      WinMartScraper(),
}

ALL_CATEGORIES = ["sua", "ruou-bia", "thuoc-la"]

_runs: dict[str, PipelineRun] = {}


def get_run(run_id: str) -> Optional[PipelineRun]:
    return _runs.get(run_id)


def list_runs() -> list[dict]:
    return [r.model_dump() for r in _runs.values()]


def create_run(sites: list[str], categories: list[str]) -> PipelineRun:
    run = PipelineRun(
        run_id=str(uuid.uuid4())[:8],
        status=PipelineStatus.QUEUED,
        sites=sites,
        categories=categories,
        sites_total=len(sites) * len(categories),
    )
    _runs[run.run_id] = run
    return run


async def _process_one(
    run: PipelineRun,
    scraper: BaseScraper,
    category: str,
    limit: int,
    use_ai: bool,
) -> None:
    site = scraper.site_name
    run.append_log(f"▶ [{site}] {category} — fetching...")

    try:
        result: ScrapeResult = await scraper.scrape(category, limit)
        products = [p.model_dump() for p in result.products]

        html_path = save_bronze(site, f"{site}/{category}", result.raw)
        bronze_id = insert_bronze_job(
            site=site,
            url=f"https://{site}/{category}",
            category=category,
            html_path=html_path,
            status="done",
        )
        run.append_log(
            f"  ✓ Bronze: {len(result.raw):,} chars → {os.path.basename(html_path)}"
        )

        if use_ai and products:
            run.append_log(f"  🧠 Gemini enhancing {len(products)} products...")
            products = await asyncio.to_thread(enhance_products, products, site, category)
            run.append_log("  ✓ AI enhancement done")

        silver_id = insert_silver(bronze_id, site, category, products)
        run.append_log(f"  ✓ Silver: {len(products)} products (id={silver_id})")

        saved = insert_gold_batch(silver_id, site, category, products)
        run.append_log(f"  ✓ Gold: {saved} products saved")

        run.products_collected += len(result.products)
        run.products_extracted += saved

    except Exception as exc:
        msg = f"  ✗ [{site}/{category}]: {exc}"
        run.append_log(msg)
        run.errors.append(msg)
        logger.error(msg)
        insert_bronze_job(
            site=site,
            url=f"https://{site}/{category}",
            category=category,
            status="error",
            error=str(exc),
        )

    finally:
        run.sites_done += 1


async def run_pipeline(
    run_id: str,
    sites: list[str],
    categories: list[str],
    use_ai_enhance: bool = True,
    limit_per_site: int = 20,
) -> None:
    run = _runs[run_id]
    run.status = PipelineStatus.RUNNING
    run.append_log(
        f"Pipeline start | id={run_id} | sites={sites} | categories={categories}"
    )
    logger.info("Pipeline %s started: %s × %s", run_id, sites, categories)

    try:
        for site_name in sites:
            scraper = SCRAPERS.get(site_name)
            if scraper is None:
                run.append_log(f"⚠ Unknown site: {site_name}, skipping")
                continue
            for category in categories:
                await _process_one(run, scraper, category, limit_per_site, use_ai_enhance)

        run.finish(PipelineStatus.DONE)
        run.append_log(
            f"✅ Done — {run.products_extracted} products, {len(run.errors)} errors"
        )
        logger.info("Pipeline %s finished: %d products", run_id, run.products_extracted)

    except Exception as exc:
        run.append_log(f"💥 Fatal error: {exc}")
        run.errors.append(str(exc))
        run.finish(PipelineStatus.ERROR)
        logger.exception("Pipeline %s fatal error", run_id)
