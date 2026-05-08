from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from src.apps.api import router as api_router
from src.core.database import init_db
from src.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title="Marketplace Smart Crawler",
    description="Nền tảng thu thập dữ liệu TMĐT tích hợp Gemini AI",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router)

_TEMPLATES = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _TEMPLATES.TemplateResponse("index.html", {"request": request})
