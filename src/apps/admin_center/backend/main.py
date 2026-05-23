from __future__ import annotations

import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Keep the package import root available for local uvicorn runs.
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))

from apps.admin_center.backend.dependencies import market_stats as _market_stats
from apps.admin_center.backend.dependencies import mongo_store, project_root as runtime_project_root
from apps.admin_center.backend.routes import auth, dashboard, dedup, extraction, health, jobs, products, sources
from apps.admin_center.backend.routes.jobs import get_jobs
from apps.admin_center.backend.settings import settings

app = FastAPI(title="Admin Center API", version="1.0.0")

cors_origins = [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health.router,
    auth.router,
    dashboard.router,
    jobs.router,
    products.router,
    extraction.router,
    dedup.router,
    sources.router,
):
    app.include_router(router)

# Backward-compatible aliases for existing tests and local debug snippets.
project_root = runtime_project_root
login_rate_limiter = auth.login_rate_limiter


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
