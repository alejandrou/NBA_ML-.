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


@pytest.fixture(autouse=True)
def _no_ambient_pgoptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's PGOPTIONS must not change what these tests expect."""
    monkeypatch.delenv("PGOPTIONS", raising=False)


@pytest.mark.unit
def test_api_engines_open_read_only_and_time_bounded_connections(
    recorded_engine_kwargs: list[dict[str, Any]],
) -> None:
    settings = Settings(
        _env_file=None, database_url=POSTGRES_URL, api_statement_timeout_seconds=12.5
    )

    db_session.create_api_engine(settings)

    assert recorded_engine_kwargs[0]["pool_pre_ping"] is True
    assert recorded_engine_kwargs[0]["connect_args"] == {
        "connect_timeout": 5,
        "options": (
            "-c default_transaction_read_only=on"
            " -c statement_timeout=12500"
            " -c idle_in_transaction_session_timeout=12500"
        ),
    }


@pytest.mark.unit
def test_api_engines_keep_options_from_the_url(
    recorded_engine_kwargs: list[dict[str, Any]],
) -> None:
    """Passing `options` replaces the URL's, so they are merged rather than dropped;
    ours come last, and the server applies the last `-c` for a setting."""
    settings = Settings(
        _env_file=None,
        database_url=(
            f"{POSTGRES_URL}?options=-c%20search_path%3Dapi%20"
            "-c%20default_transaction_read_only%3Doff"
        ),
        api_statement_timeout_seconds=1.0,
    )

    db_session.create_api_engine(settings)

    assert recorded_engine_kwargs[0]["connect_args"]["options"] == (
        "-c search_path=api -c default_transaction_read_only=off"
        " -c default_transaction_read_only=on"
        " -c statement_timeout=1000"
        " -c idle_in_transaction_session_timeout=1000"
    )


@pytest.mark.unit
def test_api_engines_keep_pgoptions_when_the_url_has_none(
    recorded_engine_kwargs: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PGOPTIONS", "-c TimeZone=UTC")
    settings = Settings(
        _env_file=None, database_url=POSTGRES_URL, api_statement_timeout_seconds=1.0
    )

    db_session.create_api_engine(settings)

    assert recorded_engine_kwargs[0]["connect_args"]["options"].startswith(
        "-c TimeZone=UTC -c default_transaction_read_only=on"
    )


@pytest.mark.unit
def test_url_options_win_over_pgoptions_as_in_libpq(
    recorded_engine_kwargs: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PGOPTIONS", "-c TimeZone=UTC")
    settings = Settings(
        _env_file=None,
        database_url=f"{POSTGRES_URL}?options=-c%20application_name%3Dapi",
        api_statement_timeout_seconds=1.0,
    )

    db_session.create_api_engine(settings)

    options = recorded_engine_kwargs[0]["connect_args"]["options"]
    assert options.startswith("-c application_name=api -c default_transaction_read_only=on")
    assert "TimeZone" not in options


@pytest.mark.unit
def test_loader_engines_stay_writable(recorded_engine_kwargs: list[dict[str, Any]]) -> None:
    db_session.create_db_engine(Settings(_env_file=None, database_url=POSTGRES_URL))

    assert "options" not in recorded_engine_kwargs[0]["connect_args"]


@pytest.mark.unit
def test_sqlite_api_engines_receive_no_postgres_options() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")

    engine = db_session.create_api_engine(settings)

    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()


@pytest.mark.unit
def test_the_api_statement_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="api_statement_timeout_seconds"):
        Settings(_env_file=None, api_statement_timeout_seconds=0)


@pytest.mark.unit
def test_analyze_is_skipped_outside_postgres() -> None:
    engine = db_session.create_db_engine(
        Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")
    )
    try:
        assert db_session.analyze_database(engine) is False
    finally:
        engine.dispose()
