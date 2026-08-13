from pathlib import Path

import pytest
from pydantic import ValidationError

from nba_data.config.settings import Settings


@pytest.mark.unit
def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://nba:nba@localhost:5432/nba"
    assert settings.database_connect_timeout_seconds == 5.0
    assert settings.api_readiness_timeout_seconds == 2.0
    assert settings.scraper_max_requests_per_minute == 10
    assert settings.scraper_min_delay_seconds == 6
    assert settings.scraper_cache_dir == Path("data/raw/html")
    assert settings.scraper_force_refresh is False


@pytest.mark.unit
def test_settings_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "5")
    monkeypatch.setenv("SCRAPER_CACHE_DIR", "tmp/html")
    monkeypatch.setenv("API_READINESS_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "3")

    settings = Settings(_env_file=None)

    assert settings.scraper_max_requests_per_minute == 5
    assert settings.scraper_cache_dir == Path("tmp/html")
    assert settings.api_readiness_timeout_seconds == 0.5
    assert settings.database_connect_timeout_seconds == 3.0


@pytest.mark.unit
def test_settings_rejects_empty_user_agent() -> None:
    with pytest.raises(ValidationError):
        Settings(scraper_user_agent=" ", _env_file=None)


@pytest.mark.unit
@pytest.mark.parametrize("timeout", [0, -1.0])
def test_settings_rejects_a_non_positive_readiness_timeout(timeout: float) -> None:
    with pytest.raises(ValidationError):
        Settings(api_readiness_timeout_seconds=timeout, _env_file=None)


@pytest.mark.unit
@pytest.mark.parametrize("timeout", [0, -1.0])
def test_settings_rejects_a_non_positive_connect_timeout(timeout: float) -> None:
    """Zero or negative means "wait forever" to libpq — the very thing this bounds."""
    with pytest.raises(ValidationError):
        Settings(database_connect_timeout_seconds=timeout, _env_file=None)
