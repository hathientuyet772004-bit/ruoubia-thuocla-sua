from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup
from urllib.request import Request, urlopen

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import pipeline_service
from apps.admin_center.backend.mongo_store import now_utc

log = logging.getLogger("admin_center.worker")

DEFAULT_USER_AGENT = "AdminCenterCrawler/0.1 (+https://localhost)"
DISCOVERY_HINTS = (
    "product",
    "products",
    "category",
    "collection",
    "collections",
    "san-pham",
    "danh-muc",
    "ruou",
    "vang",
    "bia",
    "whisky",
    "wine",
)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def fetch_url(url: str, user_agent: str | None, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    headers = {
        "User-Agent": user_agent or DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout_seconds) as response:
        content = response.read()
        return content, {
            "status_code": getattr(response, "status", None),
            "content_type": response.headers.get("content-type", "text/html"),
            "final_url": response.geturl(),
        }


def discover_links(html: bytes, base_url: str, max_links: int) -> list[str]:
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return []
    base = urlparse(base_url)
    links = []
    seen = set()
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urldefrag(urljoin(base_url, href))[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc:
            continue
        path = parsed.path.lower()
        if "." in path.rsplit("/", 1)[-1]:
            continue
        score = 1 if any(hint in path for hint in DISCOVERY_HINTS) else 0
        key = absolute.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        links.append((score, key))
    links.sort(key=lambda item: item[0], reverse=True)
    return [url for _, url in links[:max_links]]


def save_capture(pipeline: dict[str, Any], url: str, content: bytes, metadata: dict[str, Any], page_type: str) -> dict[str, Any]:
    parsed = urlparse(metadata.get("final_url") or url)
    domain = parsed.netloc.lower()
    raw_page_id = str(uuid.uuid4())
    page = deps.mongo_store.save_raw_page_content(
        {
            "raw_page_id": raw_page_id,
            "domain": domain,
            "url": metadata.get("final_url") or url,
            "page_type": page_type,
            "content_type": metadata.get("content_type") or "text/html",
            "status": "completed",
            "task_id": f"worker-{raw_page_id}",
            "pipeline_id": pipeline.get("pipeline_id"),
            "metadata": {
                "filename": f"{domain}-{raw_page_id}.html",
                "source": "worker",
                "status_code": metadata.get("status_code"),
                "truncated": bool(metadata.get("truncated")),
            },
        },
        content,
    )
    return {
        "raw_page_id": page["raw_page_id"],
        "domain": domain,
        "url": page.get("url"),
        "content_length": page.get("content_length"),
    }


def capture_entry_urls(pipeline: dict[str, Any]) -> list[dict[str, Any]]:
    db = deps.mongo_store.get_db()
    if db is None:
        raise RuntimeError("MongoDB Atlas is unavailable")

    timeout_seconds = env_int("WORKER_FETCH_TIMEOUT_SECONDS", 30)
    max_bytes = env_int("WORKER_MAX_RESPONSE_BYTES", 5_000_000)
    page_budget = max(1, int(pipeline.get("page_budget") or env_int("WORKER_PAGE_BUDGET", 20)))
    max_depth = max(0, int(pipeline.get("max_depth") or 0))
    captured = []
    warnings = []
    queued = [(str(url or "").strip(), 0) for url in pipeline.get("entry_urls") or [] if str(url or "").strip()]
    seen_urls = set()

    while queued and len(captured) < page_budget:
        url, depth = queued.pop(0)
        url = url.rstrip("/")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            warnings.append(f"{url}: invalid URL")
            continue

        try:
            content, metadata = fetch_url(url, pipeline.get("user_agent"), timeout_seconds)
            if len(content) > max_bytes:
                content = content[:max_bytes]
                metadata["truncated"] = True
            captured.append(save_capture(pipeline, url, content, metadata, "entry" if depth == 0 else "discovered"))
            if depth < max_depth and len(captured) < page_budget:
                remaining = page_budget - len(captured)
                for link in discover_links(content, metadata.get("final_url") or url, remaining * 3):
                    if link not in seen_urls:
                        queued.append((link, depth + 1))
        except HTTPError as exc:
            warnings.append(f"{url}: HTTP {exc.code}")
        except (TimeoutError, URLError) as exc:
            warnings.append(f"{url}: {exc}")

    if captured or warnings:
        db.admin_pipeline_worker_events.insert_one({
            "event_id": str(uuid.uuid4()),
            "pipeline_id": pipeline.get("pipeline_id"),
            "event": "entry_url_capture",
            "captured": captured,
            "warnings": warnings,
            "created_at": now_utc(),
        })
    return captured


def run_is_due(pipeline: dict[str, Any], now: datetime, default_interval_seconds: int, run_manual: bool) -> bool:
    if not pipeline.get("enabled", True):
        return False
    if pipeline.get("schedule_type") == "manual" and not run_manual:
        return False

    interval_seconds = default_interval_seconds
    cron = str(pipeline.get("cron") or "").strip()
    if cron.startswith("*/"):
        try:
            interval_seconds = max(60, int(cron.split()[0][2:]) * 60)
        except (IndexError, ValueError):
            interval_seconds = default_interval_seconds

    last_run_at = pipeline.get("last_run_at")
    if not isinstance(last_run_at, datetime):
        return True
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if last_run_at.tzinfo is None:
        last_run_at = last_run_at.replace(tzinfo=timezone.utc)
    return now - last_run_at >= timedelta(seconds=interval_seconds)


def process_due_pipelines() -> int:
    db = deps.mongo_store.get_db()
    if db is None:
        log.warning("MongoDB Atlas is unavailable; worker cycle skipped.")
        return 0

    default_interval_seconds = env_int("WORKER_RUN_INTERVAL_SECONDS", 300)
    run_manual = env_bool("WORKER_RUN_MANUAL_PIPELINES", True)
    now = now_utc()
    pipelines = list(db.admin_pipelines.find({"enabled": True}, {"_id": False}))
    processed = 0

    for pipeline in pipelines:
        if not run_is_due(pipeline, now, default_interval_seconds, run_manual):
            continue
        pipeline_id = pipeline.get("pipeline_id")
        if not pipeline_id:
            continue
        log.info("Running pipeline %s", pipeline_id)
        try:
            capture_entry_urls(pipeline)
            pipeline_service.run_pipeline(str(pipeline_id))
            processed += 1
        except Exception as exc:  # pragma: no cover - worker must keep running after one bad source
            log.exception("Pipeline %s failed in worker: %s", pipeline_id, exc)
            db.admin_pipeline_worker_events.insert_one({
                "event_id": str(uuid.uuid4()),
                "pipeline_id": pipeline_id,
                "event": "worker_error",
                "error": str(exc),
                "created_at": now_utc(),
            })
    return processed


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    poll_seconds = env_int("WORKER_POLL_SECONDS", 60)
    log.info("Admin Center worker started; polling every %ss.", poll_seconds)
    while True:
        process_due_pipelines()
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
