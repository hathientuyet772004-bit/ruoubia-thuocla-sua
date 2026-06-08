from __future__ import annotations

import logging
import os
import re
import socket
import time
import uuid
import traceback
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.parse import urljoin, urldefrag
import ipaddress

import chardet
from bs4 import BeautifulSoup
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from apps.admin_center.backend import dependencies as deps
from apps.admin_center.backend import pipeline_service
from apps.admin_center.backend.mongo_store import now_utc

log = logging.getLogger("admin_center.worker")

DEFAULT_USER_AGENT = "AdminCenterCrawler/0.1 (+https://localhost)"
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 1.5
DEFAULT_BROWSER_WAIT_SECONDS = 15
COMMON_SITEMAP_PATHS = ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml")
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
JS_RENDER_HINTS = (
    "__next_data__",
    "__nuxt__",
    "window.__apollo_state__",
    "data-reactroot",
    "hydrate",
    "window.__initial_state__",
)
BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


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


def local_job_dir(domain: str, task_id: str) -> Path:
    return deps.project_root / "store" / "raw" / domain / task_id


def write_local_job_metadata(domain: str, task_id: str, metadata: dict[str, Any]) -> Path:
    meta_path = Path(f"{local_job_dir(domain, task_id)}.meta.json")
    deps.write_json(meta_path, metadata)
    return meta_path


def write_local_job_error(domain: str, task_id: str, error_text: str) -> Path:
    error_path = Path(f"{local_job_dir(domain, task_id)}.error")
    error_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.write_text(error_text, encoding="utf-8")
    return error_path


def fetch_url(url: str, user_agent: str | None, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    validate_public_fetch_url(url)
    headers = {
        "User-Agent": user_agent or DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    request = Request(url, headers=headers)
    with safe_urlopen(request, timeout=timeout_seconds) as response:
        final_url = response.geturl()
        validate_public_fetch_url(final_url)
        content = response.read()
        return content, {
            "status_code": getattr(response, "status", None),
            "content_type": response.headers.get("content-type", "text/html"),
            "final_url": final_url,
        }


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_public_fetch_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_urlopen(request: Request, timeout: int):  # type: ignore[no-untyped-def]
    return build_opener(SafeRedirectHandler).open(request, timeout=timeout)


def validate_public_fetch_url(url: str) -> None:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"Unsafe fetch URL: {url}")
    host = parsed.hostname.strip().lower().rstrip(".")
    if host in BLOCKED_HOSTS:
        raise ValueError(f"Unsafe fetch host: {host}")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        # Test domains and temporarily unresolved public domains should fail at fetch time, not validation time.
        return
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(f"Unsafe fetch IP for {host}: {ip}")


def fetch_url_with_retry(
    url: str,
    user_agent: str | None,
    timeout_seconds: int,
    *,
    attempts: int,
    base_backoff_seconds: float,
) -> tuple[bytes, dict[str, Any]]:
    attempts = max(1, attempts)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch_url(url, user_agent, timeout_seconds)
        except HTTPError as exc:
            last_error = exc
            retriable = exc.code in {429, 500, 502, 503, 504}
            if not retriable or attempt >= attempts:
                raise
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            if attempt >= attempts:
                raise
        delay = min(max(base_backoff_seconds, 0.1) * (2 ** (attempt - 1)), 30.0)
        time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to fetch {url}")


def decode_bytes(content: bytes, content_type: str | None = None) -> str:
    detected = chardet.detect(content or b"")
    encoding = detected.get("encoding") or "utf-8"
    try:
        return content.decode(encoding, errors="ignore")
    except LookupError:
        return content.decode("utf-8", errors="ignore")


def parse_same_domain_links(html: bytes, base_url: str, max_links: int) -> list[str]:
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
        score = 2 if any(hint in path for hint in DISCOVERY_HINTS) else 0
        if "/san-pham/" in path:
            score += 3
        if "/danh-muc/" in path or "/category/" in path:
            score += 2
        key = absolute.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        links.append((score, key))
    links.sort(key=lambda item: item[0], reverse=True)
    return [url for _, url in links[:max_links]]


def parse_sitemap_urls(xml_text: str, base_url: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    ns = ""
    if "}" in root.tag:
        ns = root.tag.split("}", 1)[0].strip("{")
    loc_path = f".//{{{ns}}}loc" if ns else ".//loc"
    urls = []
    base = urlparse(base_url)
    for loc in root.findall(loc_path):
        value = (loc.text or "").strip()
        if not value:
            continue
        absolute = urldefrag(urljoin(base_url, value))[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc:
            continue
        urls.append(absolute.rstrip("/"))
    return urls


def discover_seed_urls(base_url: str, user_agent: str | None, timeout_seconds: int, attempts: int, backoff_seconds: float, limit: int) -> list[str]:
    base = urlparse(base_url)
    if not base.scheme or not base.netloc:
        return []
    seeds: list[str] = []
    seen = set()
    sitemap_queue = deque()

    def add_seed(value: str) -> None:
        key = value.rstrip("/")
        if key and key not in seen and urlparse(key).netloc == base.netloc:
            seen.add(key)
            seeds.append(key)

    for path in COMMON_SITEMAP_PATHS:
        sitemap_queue.append(urljoin(f"{base.scheme}://{base.netloc}", path))

    while sitemap_queue and len(seeds) < limit:
        sitemap_url = sitemap_queue.popleft()
        try:
            content, metadata = fetch_url_with_retry(
                sitemap_url,
                user_agent,
                timeout_seconds,
                attempts=2,
                base_backoff_seconds=0.5,
            )
        except Exception:
            continue

        text = decode_bytes(content, metadata.get("content_type"))
        if sitemap_url.endswith("robots.txt"):
            for line in text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_queue.append(urljoin(sitemap_url, line.split(":", 1)[1].strip()))
            continue

        for discovered in parse_sitemap_urls(text, sitemap_url):
            if len(seeds) >= limit:
                break
            if "/sitemap" in sitemap_url and discovered.endswith(".xml") and discovered not in sitemap_queue:
                sitemap_queue.append(discovered)
                continue
            add_seed(discovered)

    return seeds[:limit]


def page_looks_dynamic(html: bytes) -> bool:
    text = decode_bytes(html, None).lower()
    link_count = text.count("<a ")
    visible_text = re.sub(r"<[^>]+>", " ", text)
    return any(hint in text for hint in JS_RENDER_HINTS) or (len(visible_text.strip()) < 500 and link_count < 5)


def fetch_url_browser(url: str, user_agent: str | None, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Playwright browser fallback is unavailable") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context_kwargs: dict[str, Any] = {}
        if user_agent:
            context_kwargs["user_agent"] = user_agent
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.set_default_timeout(max(1, timeout_seconds) * 1000)
        try:
            page.goto(url, wait_until="networkidle")
            content = page.content().encode("utf-8")
            return content, {
                "status_code": 200,
                "content_type": "text/html",
                "final_url": page.url,
                "rendered_with": "playwright",
            }
        except PlaywrightTimeoutError as exc:  # pragma: no cover - optional dependency
            raise TimeoutError(str(exc)) from exc
        finally:
            browser.close()


def fetch_url_best(
    url: str,
    pipeline: dict[str, Any],
    timeout_seconds: int,
    attempts: int,
    backoff_seconds: float,
) -> tuple[bytes, dict[str, Any]]:
    content, metadata = fetch_url_with_retry(
        url,
        pipeline.get("user_agent"),
        timeout_seconds,
        attempts=attempts,
        base_backoff_seconds=backoff_seconds,
    )
    browser_enabled = env_bool("WORKER_BROWSER_FALLBACK", False) or bool(pipeline.get("browser_fallback"))
    if browser_enabled and page_looks_dynamic(content):
        try:
            browser_content, browser_metadata = fetch_url_browser(url, pipeline.get("user_agent"), max(timeout_seconds, DEFAULT_BROWSER_WAIT_SECONDS))
            if len(browser_content) >= len(content):
                return browser_content, browser_metadata
        except Exception as exc:
            log.info("Browser fallback skipped for %s: %s", url, exc)
    return content, metadata


def save_capture(pipeline: dict[str, Any], url: str, content: bytes, metadata: dict[str, Any], page_type: str) -> dict[str, Any]:
    parsed = urlparse(metadata.get("final_url") or url)
    domain = parsed.netloc.lower()
    raw_page_id = str(uuid.uuid4())
    task_id = f"worker-{raw_page_id}"
    local_metadata = {
        "domain": domain,
        "url": metadata.get("final_url") or url,
        "page_type": page_type,
        "status_code": metadata.get("status_code"),
        "content_type": metadata.get("content_type") or "text/html",
        "truncated": bool(metadata.get("truncated")),
        "source": "worker",
        "filename": f"{domain}-{raw_page_id}.html",
        "task_id": task_id,
        "raw_page_id": raw_page_id,
        "captured_at": now_utc().isoformat(),
    }
    write_local_job_metadata(domain, task_id, local_metadata)
    try:
        page = deps.mongo_store.save_raw_page_content(
            {
                "raw_page_id": raw_page_id,
                "domain": domain,
                "url": metadata.get("final_url") or url,
                "page_type": page_type,
                "content_type": metadata.get("content_type") or "text/html",
                "status": "completed",
                "task_id": task_id,
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
    except Exception:
        write_local_job_error(domain, task_id, traceback.format_exc())
        raise
    write_local_job_metadata(domain, task_id, {
        **local_metadata,
        "status": "completed",
        "content_length": page.get("content_length"),
        "updated_at": now_utc().isoformat(),
    })
    return {
        "raw_page_id": page["raw_page_id"],
        "domain": domain,
        "url": page.get("url"),
        "content_length": page.get("content_length"),
    }


def recently_captured_url(db: Any, url: str, min_hours: int) -> bool:
    if min_hours <= 0:
        return False
    cutoff = now_utc() - timedelta(hours=min_hours)
    try:
        doc = db.sc_raw_pages.find_one(
            {"url": url, "captured_at": {"$gte": cutoff}},
            {"_id": False, "raw_page_id": True},
        )
    except Exception:
        return False
    return isinstance(doc, dict) and bool(doc.get("raw_page_id"))


def capture_entry_urls(pipeline: dict[str, Any]) -> list[dict[str, Any]]:
    db = deps.mongo_store.get_db()
    if db is None:
        raise RuntimeError("MongoDB Atlas is unavailable")

    timeout_seconds = env_int("WORKER_FETCH_TIMEOUT_SECONDS", 30)
    max_bytes = env_int("WORKER_MAX_RESPONSE_BYTES", 1_000_000)
    configured_budget = max(1, int(pipeline.get("page_budget") or env_int("WORKER_PAGE_BUDGET", 10)))
    page_budget = min(configured_budget, max(1, env_int("WORKER_MAX_PAGE_BUDGET", 20)))
    max_depth = max(0, int(pipeline.get("max_depth") or 0))
    recrawl_min_hours = env_int("WORKER_RECRAWL_MIN_HOURS", 24)
    retry_attempts = max(1, int(pipeline.get("retry_attempts") or env_int("WORKER_FETCH_RETRY_ATTEMPTS", DEFAULT_RETRY_ATTEMPTS)))
    retry_backoff_seconds = float(pipeline.get("retry_backoff_seconds") or env_int("WORKER_FETCH_BACKOFF_SECONDS", DEFAULT_RETRY_BACKOFF_SECONDS))
    captured = []
    warnings = []
    seeds = []
    for url in pipeline.get("entry_urls") or []:
        value = str(url or "").strip()
        if value:
            seeds.append(value)
    base_url = seeds[0] if seeds else ""
    if base_url:
        seeds.extend(discover_seed_urls(base_url, pipeline.get("user_agent"), timeout_seconds, retry_attempts, retry_backoff_seconds, max(10, page_budget)))
    queued = deque((url.rstrip("/"), 0) for url in dict.fromkeys(seeds))
    seen_urls = set()

    while queued and len(captured) < page_budget:
        url, depth = queued.popleft()
        url = url.rstrip("/")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            warnings.append(f"{url}: invalid URL")
            continue
        if recently_captured_url(db, url, recrawl_min_hours):
            warnings.append(f"{url}: skipped because it was captured within {recrawl_min_hours}h")
            continue

        try:
            content, metadata = fetch_url_best(url, pipeline, timeout_seconds, retry_attempts, retry_backoff_seconds)
            if len(content) > max_bytes:
                content = content[:max_bytes]
                metadata["truncated"] = True
            captured.append(save_capture(pipeline, url, content, metadata, "entry" if depth == 0 else "discovered"))
            if depth < max_depth and len(captured) < page_budget:
                remaining = page_budget - len(captured)
                for link in parse_same_domain_links(content, metadata.get("final_url") or url, remaining * 3):
                    if link not in seen_urls:
                        queued.append((link, depth + 1))
        except HTTPError as exc:
            warnings.append(f"{url}: HTTP {exc.code}")
        except (TimeoutError, URLError, ValueError) as exc:
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
    run_manual = env_bool("WORKER_RUN_MANUAL_PIPELINES", False)
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
            pipeline_service.run_collection_pipeline(str(pipeline_id), capture_entry_urls)
            processed += 1
        except Exception as exc:  # pragma: no cover - worker must keep running after one bad source
            log.exception("Pipeline %s failed in worker: %s", pipeline_id, exc)
            try:
                db.admin_pipeline_worker_events.insert_one({
                    "event_id": str(uuid.uuid4()),
                    "pipeline_id": pipeline_id,
                    "event": "worker_error",
                    "error": str(exc),
                    "created_at": now_utc(),
                })
            except Exception:
                log.warning("Could not persist worker_error for %s because Mongo writes are blocked.", pipeline_id)
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
