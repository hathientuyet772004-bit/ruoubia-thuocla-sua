"""
API endpoints cho pipeline điều khiển.
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from typing import Optional

from src.core.database import init_db, get_stats, get_gold_products, get_recent_jobs
from src.modules.scraper.engine import run_pipeline, get_run_status, list_runs
from src.modules.detector.ai_extractor import analyze_site_structure
import httpx

router = APIRouter(prefix="/api")


@router.get("/stats")
async def stats():
    init_db()
    return get_stats()


@router.post("/pipeline/run")
async def start_pipeline(
    background_tasks: BackgroundTasks,
    sites: Optional[str] = Query(None, description="Comma-separated sites: tiki,bachhoaxanh,winmart"),
    categories: Optional[str] = Query(None, description="Comma-separated: sua,ruou-bia,thuoc-la"),
    ai_enhance: bool = Query(True),
    limit: int = Query(20),
):
    site_list = [s.strip() for s in sites.split(",")] if sites else None
    cat_list = [c.strip() for c in categories.split(",")] if categories else None

    run_id_holder = {}

    async def _run():
        rid = await run_pipeline(
            sites=site_list,
            categories=cat_list,
            use_ai_enhance=ai_enhance,
            limit_per_site=limit,
        )
        run_id_holder["run_id"] = rid

    task = asyncio.create_task(run_pipeline(
        sites=site_list,
        categories=cat_list,
        use_ai_enhance=ai_enhance,
        limit_per_site=limit,
    ))

    return {"message": "Pipeline started", "note": "Check /api/pipeline/runs for status"}


@router.get("/pipeline/runs")
async def pipeline_runs():
    return list_runs()


@router.get("/pipeline/run/{run_id}")
async def pipeline_run_status(run_id: str):
    return get_run_status(run_id)


@router.get("/products")
async def products(
    category: Optional[str] = None,
    site: Optional[str] = None,
    limit: int = 100,
):
    init_db()
    return get_gold_products(category=category, site=site, limit=limit)


@router.get("/jobs")
async def recent_jobs(limit: int = 20):
    init_db()
    return get_recent_jobs(limit=limit)


@router.post("/detect")
async def detect_site(url: str = Query(...)):
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            html = resp.text
        result = await asyncio.to_thread(analyze_site_structure, html, url)
        return result
    except Exception as e:
        return {"error": str(e)}
