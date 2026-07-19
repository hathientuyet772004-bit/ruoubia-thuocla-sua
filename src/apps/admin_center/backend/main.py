from __future__ import annotations

import logging
import os
import sys
import time
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Keep the package import root available for local uvicorn runs.
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))

from apps.admin_center.backend.dependencies import market_stats as _market_stats
from apps.admin_center.backend.dependencies import data_store, project_root as runtime_project_root
from apps.admin_center.backend.routes import auth, dashboard, dedup, extraction, health, jobs, pipelines, products, sources
from apps.admin_center.backend.routes.jobs import get_jobs
from apps.admin_center.backend.settings import settings

app = FastAPI(title="Admin Center API", version="1.0.0")
log = logging.getLogger("uvicorn.error")


@app.on_event("startup")
async def startup_checks() -> None:
    """Verify critical dependencies at boot and start background services."""
    # 1. Database connectivity check
    if data_store.ready():
        log.info("✔  Database: PostgreSQL connected (AdminPgStore ready)")
    else:
        log.error(
            "✘  Database: PostgreSQL NOT connected — all Admin Center data will be unavailable. "
            "Ensure DATABASE_URL is set and the PostgreSQL instance is reachable."
        )

    # 2. Gemini API key check
    from apps.admin_center.backend.settings import settings as _settings
    if _settings.GEMINI_API_KEY:
        log.info("✔  Gemini API: key configured")
    else:
        log.warning("⚠  Gemini API: GEMINI_API_KEY not set — AI features (rule generation, review) will be unavailable")

    # 3. Cron worker — runs process_due_pipelines() on every poll interval
    from apps.admin_center.backend.worker import process_due_pipelines
    _poll_seconds = max(10, int(os.environ.get("WORKER_POLL_SECONDS", "60")))

    def _worker_loop() -> None:
        log.info("✔  Cron worker: polling every %ss", _poll_seconds)
        while True:
            try:
                processed = process_due_pipelines()
                if processed:
                    log.info("Cron worker: ran %s pipeline(s)", processed)
            except Exception as exc:
                log.exception("Cron worker cycle failed: %s", exc)
            time.sleep(_poll_seconds)

    _cron_thread = threading.Thread(target=_worker_loop, name="pipeline-cron", daemon=True)
    _cron_thread.start()

cors_origins = [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    """Log per-route processing time so slow API paths are visible in Docker logs."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    log.info("%s %s -> %s %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    return response

for router in (
    health.router,
    auth.router,
    dashboard.router,
    jobs.router,
    products.router,
    extraction.router,
    pipelines.router,
    dedup.router,
    sources.router,
):
    app.include_router(router)

# Backward-compatible aliases for existing tests and local debug snippets.
project_root = runtime_project_root
login_rate_limiter = auth.login_rate_limiter


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
