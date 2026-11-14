"""The API's connections are read-only and time-bounded in PostgreSQL itself, not only in code."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from nba_data.config.settings import get_settings
from nba_data.db.session import create_api_engine

pytestmark = pytest.mark.integration

_READ_ONLY_TRANSACTION_SQLSTATE = "25006"


@pytest.fixture
def api_engine(postgres_engine: Engine) -> Iterator[Engine]:
    # `postgres_engine` first: it refuses an unauthorized or non-disposable database.
    engine = create_api_engine(get_settings())
    try:
        yield engine
    finally:
        engine.dispose()


def test_api_connections_refuse_writes(api_engine: Engine) -> None:
    with api_engine.connect() as connection:
        assert connection.scalar(text("SHOW transaction_read_only")) == "on"
        with pytest.raises(DBAPIError) as raised:
            connection.execute(text("CREATE TEMPORARY TABLE api_write_probe (id integer)"))
        assert getattr(raised.value.orig, "sqlstate", None) == _READ_ONLY_TRANSACTION_SQLSTATE


def test_api_connections_carry_the_configured_time_bounds(api_engine: Engine) -> None:
    expected = f"{int(get_settings().api_statement_timeout_seconds * 1000)}ms"
    with api_engine.connect() as connection:
        statement = connection.scalar(text("SELECT current_setting('statement_timeout')"))
        idle = connection.scalar(
            text("SELECT current_setting('idle_in_transaction_session_timeout')")
        )
    # PostgreSQL reports in its own units (e.g. "30s"); compare in milliseconds.
    assert _milliseconds(statement) == _milliseconds(expected)
    assert _milliseconds(idle) == _milliseconds(expected)


def _milliseconds(setting: str) -> int:
    units = {"ms": 1, "s": 1000, "min": 60_000, "h": 3_600_000}
    for suffix in ("ms", "min", "s", "h"):
        if setting.endswith(suffix):
            return int(setting.removesuffix(suffix)) * units[suffix]
    return int(setting)
