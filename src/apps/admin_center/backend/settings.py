from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[4]
DEFAULT_ADMIN_PASSWORD = "admin"
DEFAULT_ADMIN_SESSION_SECRET = "dev-admin-session-secret"


class Settings(BaseSettings):
    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    MONGODB_URI: str = ""
    MONGODB_DB: str = "auto_collection_data_marketing"
    MONGODB_TIMEOUT_MS: int = 10000
    CORS_ALLOW_ORIGINS: str = "http://localhost"
    ADMIN_PASSWORD: str = DEFAULT_ADMIN_PASSWORD
    ADMIN_SESSION_SECRET: str = DEFAULT_ADMIN_SESSION_SECRET
    ADMIN_SESSION_TTL_SECONDS: int = 28800

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_production_config(self) -> None:
        if self.ENV.lower() != "production":
            return
        failures = []
        if self.ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
            failures.append("ADMIN_PASSWORD must be changed in production")
        if self.ADMIN_SESSION_SECRET == DEFAULT_ADMIN_SESSION_SECRET:
            failures.append("ADMIN_SESSION_SECRET must be changed in production")
        if len(self.ADMIN_SESSION_SECRET) < 32:
            failures.append("ADMIN_SESSION_SECRET must be at least 32 characters in production")
        if failures:
            raise RuntimeError("; ".join(failures))


settings = Settings()
settings.validate_production_config()
