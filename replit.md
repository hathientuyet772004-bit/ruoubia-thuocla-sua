# Marketplace Smart Crawler & Lakehouse Platform

## Project Overview
A modern data platform that automates collection, analysis, and management of market data (Alcohol, Tobacco, Milk) from major Vietnamese e-commerce platforms. Uses Gemini AI for site discovery and a Medallion Lakehouse architecture for data processing.

## Architecture
- **Bronze Layer**: MinIO (Raw HTML/MHTML storage)
- **Silver Layer**: PostgreSQL JSONB (structured intermediate data)
- **Gold Layer**: PostgreSQL (clean, normalized, BI-ready)
- **AI Engine**: Google Gemini 1.5 Flash
- **Orchestration**: Apache Airflow
- **Scraping**: Playwright
- **Deduplication**: Redis

## Running the App
The FastAPI dashboard runs on port 5000:
```bash
pip install -r requirements.txt
python main.py
```

## Project Structure
- `src/modules/detector/` - AI site structure mapping & strategy diagnosis
- `src/modules/scraper/` - Automated scraping engine (Playwright)
- `src/modules/collector/` - Web Collector App for high-security sites
- `src/apps/` - FastAPI backend & dashboard
- `src/core/` - Core shared logic (DB, Storage, Logging)
- `infra/` - Docker, Airflow DAGs, DB migrations
- `scripts/` - Operational scripts

## Environment Variables
Copy `.env.example` to `.env` and fill in:
- `GEMINI_API_KEY` - Google AI Studio API key
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` - MinIO credentials

## User Preferences
- Vietnamese-language project; UI text may be in Vietnamese
- Uses Medallion Lakehouse architecture pattern
- Python 3.11+ environment on Replit (no Docker)
