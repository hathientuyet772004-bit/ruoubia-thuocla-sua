from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    MONGODB_URI: str = ""
    MONGODB_DB: str = "auto_collection_data_marketing"
    MONGODB_TIMEOUT_MS: int = 10000
    CORS_ALLOW_ORIGINS: str = "http://localhost"
    ADMIN_PASSWORD: str = "admin"
    ADMIN_SESSION_SECRET: str = "dev-admin-session-secret"
    ADMIN_SESSION_TTL_SECONDS: int = 28800

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
