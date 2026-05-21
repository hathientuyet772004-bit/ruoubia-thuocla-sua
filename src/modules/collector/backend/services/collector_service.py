from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from shared.config import settings
from db.database import SessionLocal
from sqlalchemy import text
from shared.services import fetch_mhtml, make_url_hash, upload_mhtml, is_url_seen, mark_url_seen, get_domain, DiscoveryService, CollectConfig

log = logging.getLogger("collector.auto_collect")




def _insert_scraped_file(*, url_hash: str, url: str, minio_path: str, source: str) -> None:
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
            INSERT INTO scraped_files (url_hash, url, minio_path, source, status, scraped_at)
            VALUES (:h, :u, :p, :s, 'pending', now())
            ON CONFLICT (url_hash) DO NOTHING
            """
            ),
            {"h": url_hash, "u": url, "p": minio_path, "s": source},
        )
        db.commit()
    finally:
        db.close()


async def collect_one_url(url: str, *, cfg: CollectConfig, source: str) -> dict:
    url_hash = make_url_hash(url)
    if is_url_seen(url_hash):
        return {"url": url, "url_hash": url_hash, "status": "skipped", "reason": "redis_seen"}

    proxy = DiscoveryService._pick_proxy(cfg)
    mhtml, _title = await fetch_mhtml(url, proxy_server=proxy)
    DiscoveryService._sleep_polite(cfg)

    minio_path = upload_mhtml(url, mhtml, domain=source, page_type="product")
    _insert_scraped_file(url_hash=url_hash, url=url, minio_path=minio_path, source=source)
    mark_url_seen(url_hash)

    return {"url": url, "url_hash": url_hash, "status": "queued", "minio_path": minio_path}


async def collect_domain_monthly(*, base_url: str, max_urls: int | None = None, cfg: CollectConfig | None = None) -> dict:
    cfg = cfg or CollectConfig()
    domain = get_domain(base_url)

    urls = DiscoveryService.discover_product_urls(base_url, cfg=cfg)
    if max_urls is not None:
        urls = urls[: int(max_urls)]

    queued = skipped = failed = 0
    samples: list[dict] = []

    # Sequential by default (safer for anti-bot). You can parallelize later with bounded concurrency.
    for u in urls:
        try:
            res = await collect_one_url(u, cfg=cfg, source=domain)
            if res["status"] == "queued":
                queued += 1
            else:
                skipped += 1
            if len(samples) < 20:
                samples.append(res)
        except Exception as e:
            failed += 1
            if len(samples) < 20:
                samples.append({"url": u, "status": "failed", "error": str(e)[:200]})

        if queued >= cfg.max_products_per_domain:
            break

    return {
        "domain": domain,
        "base_url": base_url,
        "discovered": len(urls),
        "queued": queued,
        "skipped": skipped,
        "failed": failed,
        "sample": samples,
    }


def list_monthly_domains() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
            SELECT domain, base_url
            FROM domains
            WHERE enabled = true AND cadence = 'monthly'
            ORDER BY domain ASC
            """
            )
        ).fetchall()
        return [{"domain": r[0], "base_url": r[1]} for r in rows]
    finally:
        db.close()
