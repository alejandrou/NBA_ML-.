from pathlib import Path

import pytest
from pydantic import ValidationError

from nba_data.config.settings import Settings


@pytest.mark.unit
def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://nba:nba@localhost:5432/nba"
    assert settings.scraper_max_requests_per_minute == 10
    assert settings.scraper_min_delay_seconds == 6
    assert settings.scraper_cache_dir == Path("data/raw/html")
    assert settings.scraper_force_refresh is False


@pytest.mark.unit
def test_settings_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "5")
    monkeypatch.setenv("SCRAPER_CACHE_DIR", "tmp/html")

    settings = Settings(_env_file=None)

    assert settings.scraper_max_requests_per_minute == 5
    assert settings.scraper_cache_dir == Path("tmp/html")


@pytest.mark.unit
def test_settings_rejects_empty_user_agent() -> None:
    with pytest.raises(ValidationError):
        Settings(scraper_user_agent=" ", _env_file=None)
