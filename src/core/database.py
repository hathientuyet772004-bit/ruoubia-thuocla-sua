import sqlite3
import json
import os
from contextlib import contextmanager

from src.core.config import settings

DB_PATH = settings.database_path


@contextmanager
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS bronze_jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            site        TEXT    NOT NULL,
            url         TEXT    NOT NULL,
            category    TEXT,
            status      TEXT    DEFAULT 'pending',
            html_path   TEXT,
            error       TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS silver_products (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            bronze_job_id  INTEGER REFERENCES bronze_jobs(id),
            site           TEXT NOT NULL,
            category       TEXT,
            raw_json       TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS gold_products (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            silver_id    INTEGER REFERENCES silver_products(id),
            site         TEXT    NOT NULL,
            category     TEXT    NOT NULL,
            name         TEXT,
            brand        TEXT,
            price        REAL,
            unit         TEXT,
            category_tag TEXT,
            image_url    TEXT,
            product_url  TEXT,
            rating       REAL    DEFAULT 0,
            sold_count   INTEGER DEFAULT 0,
            created_at   TEXT    DEFAULT (datetime('now'))
        );
        """)


def insert_bronze_job(
    site: str, url: str, category: str,
    html_path: str | None = None,
    status: str = "done",
    error: str | None = None,
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO bronze_jobs (site, url, category, status, html_path, error) VALUES (?,?,?,?,?,?)",
            (site, url, category, status, html_path, error),
        )
        return cur.lastrowid


def insert_silver(bronze_job_id: int, site: str, category: str, products: list) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO silver_products (bronze_job_id, site, category, raw_json) VALUES (?,?,?,?)",
            (bronze_job_id, site, category, json.dumps(products, ensure_ascii=False)),
        )
        return cur.lastrowid


def insert_gold_batch(silver_id: int, site: str, category: str, products: list) -> int:
    rows = [
        (
            silver_id, site, category,
            p.get("name"), p.get("brand"), p.get("price"),
            p.get("unit"), p.get("category_tag"),
            p.get("image_url"), p.get("product_url"),
            p.get("rating", 0), p.get("sold_count", 0),
        )
        for p in products
    ]
    with get_db() as conn:
        conn.executemany(
            """INSERT INTO gold_products
               (silver_id, site, category, name, brand, price, unit, category_tag,
                image_url, product_url, rating, sold_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
    return len(rows)


def query_gold_products(
    category: str | None = None,
    site: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = "SELECT * FROM gold_products WHERE 1=1"
    params: list = []
    if category:
        query += " AND category=?"
        params.append(category)
    if site:
        query += " AND site=?"
        params.append(site)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_db() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def query_bronze_jobs(limit: int = 50) -> list[dict]:
    with get_db() as conn:
        return [
            dict(r) for r in
            conn.execute("SELECT * FROM bronze_jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        ]


def query_stats() -> dict:
    with get_db() as conn:
        bronze = conn.execute("SELECT COUNT(*) FROM bronze_jobs WHERE status='done'").fetchone()[0]
        silver = conn.execute("SELECT COUNT(*) FROM silver_products").fetchone()[0]
        gold   = conn.execute("SELECT COUNT(*) FROM gold_products").fetchone()[0]
        sites  = conn.execute("SELECT COUNT(DISTINCT site) FROM gold_products").fetchone()[0]
        by_site = {
            r[0]: r[1] for r in
            conn.execute("SELECT site, COUNT(*) FROM gold_products GROUP BY site").fetchall()
        }
        by_cat = {
            r[0]: r[1] for r in
            conn.execute("SELECT category, COUNT(*) FROM gold_products GROUP BY category").fetchall()
        }
    return {
        "bronze_collected": bronze,
        "silver_processed": silver,
        "gold_products": gold,
        "sites": sites,
        "by_site": by_site,
        "by_category": by_cat,
    }
