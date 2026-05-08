"""
REST API — pipeline control, data retrieval, AI site analysis.
"""
import asyncio
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.core.database import (
    init_db, query_stats, query_gold_products, query_bronze_jobs,
)
from src.core.config import settings
from src.modules.detector.ai_extractor import analyze_site
from src.modules.scraper.engine import (
    SCRAPERS, ALL_CATEGORIES,
    create_run, get_run, list_runs, run_pipeline,
)

router = APIRouter(prefix="/api")


class PipelineRequest(BaseModel):
    sites: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    ai_enhance: bool = True
    limit: int = 20


class PipelineStarted(BaseModel):
    run_id: str
    status: str
    sites: list[str]
    categories: list[str]
    sites_total: int


@router.get("/stats")
async def stats():
    return query_stats()


@router.post("/pipeline/run", response_model=PipelineStarted)
async def start_pipeline(req: PipelineRequest):
    selected_sites = req.sites or list(SCRAPERS.keys())
    selected_cats  = req.categories or ALL_CATEGORIES
    limit          = max(1, min(req.limit, 100))

    invalid_sites = [s for s in selected_sites if s not in SCRAPERS]
    if invalid_sites:
        raise HTTPException(400, f"Unknown sites: {invalid_sites}. Valid: {list(SCRAPERS.keys())}")

    run = create_run(selected_sites, selected_cats)

    asyncio.create_task(
        run_pipeline(
            run_id=run.run_id,
            sites=selected_sites,
            categories=selected_cats,
            use_ai_enhance=req.ai_enhance,
            limit_per_site=limit,
        )
    )

    return PipelineStarted(
        run_id=run.run_id,
        status=run.status.value,
        sites=run.sites,
        categories=run.categories,
        sites_total=run.sites_total,
    )


@router.get("/pipeline/runs")
async def pipeline_runs():
    return list_runs()


@router.get("/pipeline/run/{run_id}")
async def pipeline_run_detail(run_id: str):
    run = get_run(run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return run.model_dump()


@router.get("/products")
async def products(
    category: Optional[str] = None,
    site: Optional[str] = None,
    limit: int = Query(default=100, le=500),
):
    return query_gold_products(category=category, site=site, limit=limit)


@router.get("/jobs")
async def jobs(limit: int = Query(default=50, le=200)):
    return query_bronze_jobs(limit=limit)


@router.post("/detect")
async def detect_site(url: str = Query(..., description="URL để Gemini phân tích")):
    try:
        async with httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
            })
            html = resp.text
        return await asyncio.to_thread(analyze_site, html, url)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Không thể tải URL: {exc}")
    except Exception as exc:
        raise HTTPException(500, str(exc))
