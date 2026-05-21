"""
Smart Crawler Management API — FastAPI Backend.
Điều khiển Crawl Jobs và Lakehouse ETL.
"""
from __future__ import annotations

import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.config import settings
from .pipeline import AdaptiveCrawler
from .lakehouse_etl import LakehouseETL
from .db_manager import DatabaseManager
from .minio_lakehouse import MinIOLakehouse

app = FastAPI(title="Smart Crawler Management API")

# Startup event to log config
@app.on_event("startup")
async def startup_event():
    settings.log_startup()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared components
db = DatabaseManager()
minio = MinIOLakehouse()

# ── Data Models ───────────────────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 5
    force: bool = False

class LakehouseProcessRequest(BaseModel):
    category: str
    domain: str
    files: Optional[List[str]] = None

# ── Background Tasks ──────────────────────────────────────────────────────────

def run_crawl_task(url: str, max_pages: int, force: bool):
    """Tiến trình crawl chạy ngầm."""
    pipeline = AdaptiveCrawler()
    try:
        pipeline.run(url, max_pages=max_pages, force_analyze=force)
    finally:
        pipeline.close()

def run_lakehouse_task(category: str, domain: str, files: Optional[List[str]]):
    """Tiến trình ETL lakehouse chạy ngầm."""
    etl = LakehouseETL()
    try:
        etl.process_domain(category, domain, files)
    finally:
        etl.db.close()

# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Smart Crawler API is running"}

# 🟢 Crawl Management

@app.get("/crawl/domains")
def list_domains():
    """Lấy danh sách các domain và trạng thái crawl."""
    sql = "SELECT * FROM sc_domains ORDER BY last_analyzed DESC"
    with db._get_conn().cursor(cursor_factory=None) as cur:
        from psycopg2.extras import RealDictCursor
        cur_dict = db._get_conn().cursor(cursor_factory=RealDictCursor)
        cur_dict.execute(sql)
        return cur_dict.fetchall()

@app.post("/crawl/run")
def trigger_crawl(req: CrawlRequest, bg_tasks: BackgroundTasks):
    """Bắt đầu một job crawl mới."""
    bg_tasks.add_task(run_crawl_task, req.url, req.max_pages, req.force)
    return {"status": "accepted", "message": f"Crawl job started for {req.url}"}

@app.get("/crawl/jobs")
def list_crawl_jobs():
    sql = "SELECT * FROM sc_crawl_jobs ORDER BY created_at DESC LIMIT 50"
    with db._get_conn().cursor(cursor_factory=None) as cur:
        from psycopg2.extras import RealDictCursor
        cur_dict = db._get_conn().cursor(cursor_factory=RealDictCursor)
        cur_dict.execute(sql)
        return cur_dict.fetchall()

# 🟣 Lakehouse Integration

@app.get("/lakehouse/categories")
def list_lakehouse_categories():
    return minio.list_categories()

@app.get("/lakehouse/{category}/domains")
def list_lakehouse_domains(category: str):
    return minio.list_domains(category)

@app.get("/lakehouse/{category}/{domain}/files")
def list_lakehouse_files(category: str, domain: str):
    return minio.list_files(category, domain)

@app.post("/lakehouse/process")
def process_lakehouse(req: LakehouseProcessRequest, bg_tasks: BackgroundTasks):
    """Bắt đầu tiến trình ETL cho Lakehouse."""
    bg_tasks.add_task(run_lakehouse_task, req.category, req.domain, req.files)
    return {"status": "accepted", "message": f"ETL job started for {req.category}/{req.domain}"}

@app.get("/lakehouse/jobs")
def list_lakehouse_jobs():
    sql = "SELECT * FROM sc_lakehouse_jobs ORDER BY created_at DESC LIMIT 50"
    with db._get_conn().cursor(cursor_factory=None) as cur:
        from psycopg2.extras import RealDictCursor
        cur_dict = db._get_conn().cursor(cursor_factory=RealDictCursor)
        cur_dict.execute(sql)
        return cur_dict.fetchall()

# 📄 Product Data

@app.get("/products")
def list_products(domain: Optional[str] = None, limit: int = 100):
    sql = "SELECT * FROM sc_products"
    params = []
    if domain:
        sql += " WHERE domain = %s"
        params.append(domain)
    sql += " ORDER BY extracted_at DESC LIMIT %s"
    params.append(limit)
    
    with db._get_conn().cursor() as cur:
        from psycopg2.extras import RealDictCursor
        cur_dict = db._get_conn().cursor(cursor_factory=RealDictCursor)
        cur_dict.execute(sql, params)
        return cur_dict.fetchall()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
