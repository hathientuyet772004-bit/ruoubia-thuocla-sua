import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/lakehouse.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS bronze_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site TEXT NOT NULL,
        url TEXT NOT NULL,
        category TEXT,
        status TEXT DEFAULT 'pending',
        html_path TEXT,
        error TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS silver_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bronze_job_id INTEGER,
        site TEXT NOT NULL,
        category TEXT,
        raw_json TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS gold_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        silver_id INTEGER,
        site TEXT NOT NULL,
        category TEXT NOT NULL,
        name TEXT,
        brand TEXT,
        price REAL,
        unit TEXT,
        image_url TEXT,
        product_url TEXT,
        rating REAL,
        sold_count INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE,
        status TEXT DEFAULT 'running',
        sites_total INTEGER DEFAULT 0,
        sites_done INTEGER DEFAULT 0,
        products_collected INTEGER DEFAULT 0,
        products_extracted INTEGER DEFAULT 0,
        error TEXT,
        started_at TEXT DEFAULT (datetime('now')),
        finished_at TEXT
    )""")

    conn.commit()
    conn.close()


def log_bronze_job(site, url, category, html_path=None, status="done", error=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO bronze_jobs (site, url, category, status, html_path, error)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (site, url, category, status, html_path, error))
    job_id = c.lastrowid
    conn.commit()
    conn.close()
    return job_id


def save_silver(bronze_job_id, site, category, raw_json):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO silver_products (bronze_job_id, site, category, raw_json, status)
        VALUES (?, ?, ?, ?, 'done')
    """, (bronze_job_id, site, category, json.dumps(raw_json, ensure_ascii=False)))
    sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid


def save_gold(silver_id, site, category, products: list):
    conn = get_conn()
    c = conn.cursor()
    for p in products:
        c.execute("""
            INSERT INTO gold_products
            (silver_id, site, category, name, brand, price, unit, image_url, product_url, rating, sold_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            silver_id, site, category,
            p.get("name"), p.get("brand"), p.get("price"),
            p.get("unit"), p.get("image_url"), p.get("product_url"),
            p.get("rating"), p.get("sold_count")
        ))
    conn.commit()
    conn.close()


def get_gold_products(category=None, site=None, limit=100):
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM gold_products WHERE 1=1"
    params = []
    if category:
        query += " AND category=?"
        params.append(category)
    if site:
        query += " AND site=?"
        params.append(site)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    stats = {}
    c.execute("SELECT COUNT(*) as n FROM bronze_jobs WHERE status='done'")
    stats["bronze_collected"] = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM silver_products")
    stats["silver_processed"] = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM gold_products")
    stats["gold_products"] = c.fetchone()["n"]
    c.execute("SELECT COUNT(DISTINCT site) as n FROM gold_products")
    stats["sites"] = c.fetchone()["n"]
    c.execute("SELECT site, COUNT(*) as n FROM gold_products GROUP BY site")
    stats["by_site"] = {r["site"]: r["n"] for r in c.fetchall()}
    c.execute("SELECT category, COUNT(*) as n FROM gold_products GROUP BY category")
    stats["by_category"] = {r["category"]: r["n"] for r in c.fetchall()}
    conn.close()
    return stats


def get_recent_jobs(limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM bronze_jobs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
