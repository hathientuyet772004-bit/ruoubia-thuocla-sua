"""
Collector Backend — FastAPI Application
Entry point: uvicorn main:app --reload
"""
import sys
import asyncio
from pathlib import Path

# Fix for Windows asyncio loop with subprocesses (required for Playwright)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Thêm dòng này để chắc chắn loop hiện tại được khởi tạo đúng loại
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.WindowsProactorEventLoop())

# Đảm bảo thư mục backend có trong Python path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import settings
from routers.proxy import router as proxy_router
from routers.stats import router as stats_router
from routers.pages import router as pages_router
from routers.interactive import router as interactive_router
from routers.collect import router as collect_router

from db.database import engine, Base
import models.orm # Ensure models are loaded

# Create tables
Base.metadata.create_all(bind=engine)

# ─── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Web Collector API",
    description="Backend proxy + data collection tool",
    version="2.0.0",
)

cors_origins = settings.cors_allow_origins_list
if cors_origins:
    allow_credentials = False if cors_origins == ["*"] else True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ─── Routers ──────────────────────────────────────────────────────
app.include_router(proxy_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(interactive_router, prefix="/api")
app.include_router(collect_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ─── Dev server ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.BACKEND_HOST, port=settings.BACKEND_PORT, reload=False, loop="asyncio")
