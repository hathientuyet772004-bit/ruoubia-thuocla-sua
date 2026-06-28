from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[4]
DEFAULT_ADMIN_PASSWORD = "admin"
DEFAULT_ADMIN_SESSION_SECRET = "dev-admin-session-secret"
PLACEHOLDER_MARKERS = ("<", ">", "CHANGE_ME", "your-domain.com")


class Settings(BaseSettings):
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    # PostgreSQL (Replit native DB — DATABASE_URL is set automatically)
    PG_URL: str = ""
    # MinIO object storage (optional; falls back to local filesystem if unset)
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "admin-center-raw"
    # Legacy MongoDB settings (kept for backward compat; no longer required)
    MONGODB_URI: str = ""
    MONGODB_DB: str = "auto_collection_data_marketing"
    MONGODB_TIMEOUT_MS: int = 10000
    CORS_ALLOW_ORIGINS: str = "http://localhost"
    ADMIN_AUTH_ENABLED: bool = False
    ADMIN_PASSWORD: str = DEFAULT_ADMIN_PASSWORD
    ADMIN_SESSION_SECRET: str = DEFAULT_ADMIN_SESSION_SECRET
    ADMIN_SESSION_TTL_SECONDS: int = 28800
    ADMIN_PRODUCT_LOCAL_FALLBACK_ENABLED: bool = False
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_HTML_EXCERPT_CHARS: int = 12000
    GEMINI_REJECTED_CANDIDATE_TTL_SECONDS: int = 21600

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_production_config(self) -> None:
        environment = self.ENV.lower()
        if environment not in {"development", "test", "production"}:
            raise RuntimeError("ENV must be one of: development, test, production")
        if environment != "production":
            return
        failures = []
        if self.ADMIN_AUTH_ENABLED:
            if self.ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
                failures.append("ADMIN_PASSWORD must be changed when admin auth is enabled")
            if "CHANGE_ME" in self.ADMIN_PASSWORD:
                failures.append("ADMIN_PASSWORD must not use placeholder values when admin auth is enabled")
            if self.ADMIN_SESSION_SECRET == DEFAULT_ADMIN_SESSION_SECRET:
                failures.append("ADMIN_SESSION_SECRET must be changed when admin auth is enabled")
            if len(self.ADMIN_SESSION_SECRET) < 32:
                failures.append("ADMIN_SESSION_SECRET must be at least 32 characters when admin auth is enabled")
            if any(marker in self.ADMIN_SESSION_SECRET for marker in PLACEHOLDER_MARKERS):
                failures.append("ADMIN_SESSION_SECRET must not use placeholder values when admin auth is enabled")
        db_url = os.environ.get("DATABASE_URL") or self.PG_URL
        if not db_url:
            failures.append("DATABASE_URL / PG_URL must be set in production (PostgreSQL connection string)")
        if self.CORS_ALLOW_ORIGINS.strip() == "*" or "your-domain.com" in self.CORS_ALLOW_ORIGINS:
            failures.append("CORS_ALLOW_ORIGINS must list real production origins")
        if failures:
            raise RuntimeError("; ".join(failures))


settings = Settings()
if not os.environ.get("ADMIN_CENTER_SKIP_AUTO_VALIDATE"):
    settings.validate_production_config()
