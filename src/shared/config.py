"""
Configuration Management — Centralized config for the entire system.
Uses Pydantic V2 Settings to load variables from the root .env file.
[SOLID: Single Responsibility] Duy nhất 1 nguồn cấu hình cho toàn hệ thống.
"""
import os
from pathlib import Path
from typing import Optional, List, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict

# Đường dẫn gốc dự án (d:\datasets\ruoubia-thuocla-sua)
# Cấu trúc: src/shared/config.py -> parent(shared) -> parent(src) -> parent(root)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    # ========================
    # ── APP & ENV ─────────────────────────────────────────────
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True
    
    # ── BACKEND ───────────────────────────────────────────────
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8080
    
    # ── CORS ──────────────────────────────────────────────────
    CORS_ALLOW_ORIGINS: str = "*"

    @property
    def cors_allow_origins_list(self) -> List[str]:
        if not self.CORS_ALLOW_ORIGINS:
            return ["*"]
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",")]

    # ========================
    # ── DATABASE ──────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "smart_crawler"
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "admin"
    DATABASE_URL: Optional[str] = None

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # ========================
    # ── MINIO ─────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "collector-store"
    MINIO_SECURE: bool = False

    @property
    def storage_dir(self) -> Path:
        path = ROOT_DIR / "store" / "raw"
        path.mkdir(exist_ok=True, parents=True)
        return path

    # ========================
    # ── REDIS ─────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # ========================
    # ── LLM (Gemini) ──────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "models/gemini-1.5-flash"
    USE_MOCK_MODE: bool = True

    # ========================
    # ── PLAYWRIGHT ────────────────────────────────────────────
    PLAYWRIGHT_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    PLAYWRIGHT_TIMEOUT_MS: int = 45000
    PLAYWRIGHT_WAIT_MS: int = 4000
    PLAYWRIGHT_VIEWPORT: Dict[str, int] = {"width": 1440, "height": 900}

    # ========================
    # ── CRAWLER PATTERNS ──────────────────────────────────────
    PRODUCT_URL_PATTERNS: List[str] = [
        r"shopee\.vn/.+-i\.\d+\.\d+",
        r"lazada\.vn/products/",
        r"tiki\.vn/.+-p\d+",
        r"sendo\.vn/.+-\d+\.html",
        r"/product/",
        r"/san-pham/",
        r"/sp/",
        r"detail",
    ]
    SEARCH_URL_PATTERNS: List[str] = [
        r"google\.com/search",
        r"bing\.com/search",
        r"/search\?",
        r"/tim-kiem",
        r"shopee\.vn/search",
    ]
    CATEGORY_URL_PATTERNS: List[str] = [
        r"/category/",
        r"/danh-muc/",
        r"/collections/",
        r"shopee\.vn/.+-cat\.",
    ]

    # Pydantic Settings Config
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )

    def log_startup(self):
        print(f"🚀 [SYSTEM] Unified Config Loaded for ENV: {self.ENV}")

# Instance duy nhất cho toàn hệ thống
settings = Settings()
