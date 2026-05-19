from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://nba:nba@localhost:5432/nba"
    app_env: str = "local"
    log_level: str = "INFO"
    scraper_user_agent: str = "nba-data-project/0.1 contact:your-email@example.com"
    scraper_max_requests_per_minute: int = Field(default=10, ge=1, le=20)
    scraper_min_delay_seconds: float = Field(default=6.0, ge=0)
    scraper_timeout_seconds: float = Field(default=30.0, gt=0)
    scraper_cache_dir: Path = Path("data/raw/html")
    scraper_force_refresh: bool = False

    @field_validator("scraper_user_agent")
    @classmethod
    def user_agent_must_be_set(cls, value: str) -> str:
        if not value.strip():
            msg = "SCRAPER_USER_AGENT must be set before making live requests"
            raise ValueError(msg)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
