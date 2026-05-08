from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI(title="Marketplace Smart Crawler - Dashboard")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/status")
async def status():
    return {
        "status": "running",
        "platform": "Marketplace Smart Crawler & Lakehouse Platform",
        "layers": {
            "bronze": "MinIO (Raw HTML/MHTML)",
            "silver": "PostgreSQL (JSONB)",
            "gold": "PostgreSQL (Normalized)"
        },
        "modules": ["detector", "scraper", "collector"],
        "ai_engine": "Gemini 1.5 Flash"
    }


@app.get("/api/domains")
async def list_domains():
    return {
        "domains": [
            {"name": "Example Market", "url": "https://example.com", "tier": "automated", "status": "pending"},
        ]
    }
