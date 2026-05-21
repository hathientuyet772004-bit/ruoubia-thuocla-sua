from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.collector_service import CollectConfig, collect_domain_monthly, list_monthly_domains

log = logging.getLogger(__name__)

router = APIRouter(tags=["collect"])


class CollectMonthlyRequest(BaseModel):
    max_urls_per_domain: Optional[int] = None


@router.get("/collect/monthly/domains")
def get_monthly_domains():
    """List enabled monthly domains from DB."""
    return {"domains": list_monthly_domains()}


@router.post("/collect/monthly")
async def run_monthly_collect(req: CollectMonthlyRequest):
    """
    Collect all enabled monthly domains:
    - discover product urls
    - capture MHTML via Playwright
    - upload to MinIO and enqueue `scraped_files` pending

    Note: runs sequentially for safety (anti-bot). Tune via env vars.
    """
    cfg = CollectConfig()
    domains = list_monthly_domains()
    results = []
    for d in domains:
        results.append(
            await collect_domain_monthly(
                base_url=d["base_url"],
                max_urls=req.max_urls_per_domain,
                cfg=cfg,
            )
        )

    totals = {
        "domains": len(results),
        "discovered": sum(r["discovered"] for r in results),
        "queued": sum(r["queued"] for r in results),
        "skipped": sum(r["skipped"] for r in results),
        "failed": sum(r["failed"] for r in results),
    }
    return {"totals": totals, "results": results}

