from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from nba_data.config.settings import Settings
from nba_data.db import session as db_session

POSTGRES_URL = "postgresql+psycopg://nba:nba@localhost:5432/nba"


@pytest.fixture
def recorded_engine_kwargs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture what `create_db_engine` asks SQLAlchemy for, without opening a connection."""
    calls: list[dict[str, Any]] = []

    def fake_create_engine(url: Any, **kwargs: Any) -> object:
        calls.append({"url": url, **kwargs})
        return object()

    monkeypatch.setattr(db_session, "create_engine", fake_create_engine)
    return calls


@pytest.mark.unit
def test_postgres_engines_bound_connection_establishment(
    recorded_engine_kwargs: list[dict[str, Any]],
) -> None:
    settings = Settings(_env_file=None, database_url=POSTGRES_URL)

    db_session.create_db_engine(settings)

    assert recorded_engine_kwargs[0]["connect_args"] == {"connect_timeout": 5}
    assert recorded_engine_kwargs[0]["pool_pre_ping"] is True


@pytest.mark.unit
def test_the_configured_connect_timeout_reaches_the_driver(
    recorded_engine_kwargs: list[dict[str, Any]],
) -> None:
    settings = Settings(
        _env_file=None, database_url=POSTGRES_URL, database_connect_timeout_seconds=9.0
    )

    db_session.create_db_engine(settings)

    assert recorded_engine_kwargs[0]["connect_args"] == {"connect_timeout": 9}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (0.5, 2),  # libpq raises anything below 2 to 2; say so instead of implying 0.5 works
        (2.0, 2),
        (2.4, 3),  # a fractional bound rounds up, never down to a tighter one
        (30.0, 30),
    ],
)
def test_connect_timeout_is_whole_seconds_and_never_below_the_libpq_floor(
    configured: float, expected: int
) -> None:
    assert db_session.connect_args_for(make_url(POSTGRES_URL), configured) == {
        "connect_timeout": expected
    }


@pytest.mark.unit
def test_non_postgres_urls_receive_no_postgres_only_connect_args() -> None:
    assert db_session.connect_args_for(make_url("sqlite+pysqlite:///:memory:"), 5.0) == {}


@pytest.mark.unit
def test_sqlite_engines_still_connect() -> None:
    """The bound is a libpq keyword; passing it to another driver would break every
    offline test and CLI run that points at SQLite."""
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")

    engine = db_session.create_db_engine(settings)

    assert isinstance(engine, Engine)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()


@pytest.mark.unit
def test_create_db_engine_falls_back_to_application_settings(
    recorded_engine_kwargs: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None, database_url=POSTGRES_URL, database_connect_timeout_seconds=7.0
    )
    monkeypatch.setattr(db_session, "get_settings", lambda: settings)

    db_session.create_db_engine()

    assert recorded_engine_kwargs[0]["connect_args"] == {"connect_timeout": 7}
