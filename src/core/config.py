from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    database_path: str = Field(default="data/lakehouse.db", alias="DATABASE_PATH")
    bronze_dir: str = Field(default="data/bronze", alias="BRONZE_DIR")

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=5000, alias="APP_PORT")

    scraper_timeout: int = Field(default=20, alias="SCRAPER_TIMEOUT")
    default_product_limit: int = Field(default=20, alias="DEFAULT_PRODUCT_LIMIT")

    model_config = {"env_file": ".env", "extra": "ignore", "populate_by_name": True}


settings = Settings()
