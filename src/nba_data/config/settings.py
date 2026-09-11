from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})

MINIMUM_SCRAPER_DELAY_SECONDS = 6.0
"""Smallest gap allowed between two Basketball Reference requests.

Repository policy, not a tuning knob: the pacing rule in ``AGENTS.md`` is a
floor, so neither configuration nor a hand-built ``Settings`` may go under it.
``BasketballReferenceClient`` clamps to the same constant.
"""


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://nba:nba@localhost:5432/nba"
    database_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    app_env: str = "local"
    log_level: str = "INFO"
    api_readiness_timeout_seconds: float = Field(default=2.0, gt=0)
    scraper_user_agent: str = "nba-data-project/0.1 contact:your-email@example.com"
    scraper_max_requests_per_minute: int = Field(default=10, ge=1, le=20)
    scraper_min_delay_seconds: float = Field(default=MINIMUM_SCRAPER_DELAY_SECONDS)
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

    @field_validator("scraper_min_delay_seconds")
    @classmethod
    def min_delay_must_respect_the_floor(cls, value: float) -> float:
        if value < MINIMUM_SCRAPER_DELAY_SECONDS:
            msg = (
                f"SCRAPER_MIN_DELAY_SECONDS={value!r} is below the "
                f"{MINIMUM_SCRAPER_DELAY_SECONDS} second minimum between Basketball "
                "Reference requests; that pacing floor is repository policy and "
                "cannot be configured away"
            )
            raise ValueError(msg)
        return value

    @field_validator("log_level")
    @classmethod
    def log_level_must_be_recognized(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in _VALID_LOG_LEVELS:
            msg = (
                f"LOG_LEVEL={value!r} is not recognized; "
                f"expected one of {sorted(_VALID_LOG_LEVELS)}"
            )
            raise ValueError(msg)
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
