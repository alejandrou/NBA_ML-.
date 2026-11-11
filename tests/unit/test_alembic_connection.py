from __future__ import annotations

import runpy
from contextlib import nullcontext
from pathlib import Path

import pytest
import sqlalchemy
from alembic import context
from alembic.config import Config

from nba_data.config import settings as settings_module
from nba_data.config.settings import Settings


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "timeout", "expected"),
    [
        ("postgresql+psycopg://nba:nba@127.0.0.1/nba", 2.4, {"connect_timeout": 3}),
        ("sqlite://", 5, {}),
    ],
)
def test_alembic_passes_the_configured_timeout_to_its_engine(monkeypatch, url, timeout, expected):
    """Execute env.py's online path without opening a PostgreSQL connection."""
    calls = []
    engine = sqlalchemy.create_engine("sqlite://")

    def recorded_engine(configuration, **kwargs):
        calls.append(kwargs)
        return engine

    monkeypatch.setattr(sqlalchemy, "engine_from_config", recorded_engine)
    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            database_url=url,
            database_connect_timeout_seconds=timeout,
        ),
    )
    monkeypatch.setattr(context, "config", Config(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(context, "configure", lambda **kwargs: None)
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    try:
        runpy.run_path(str(Path(__file__).resolve().parents[2] / "alembic/env.py"))
        assert calls[0]["connect_args"] == expected
    finally:
        engine.dispose()
