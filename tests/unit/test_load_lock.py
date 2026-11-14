"""One load at a time (DATABASE_AUDIT_2026-11-10, R-02): the CLI side.

The lock itself is exercised on PostgreSQL in tests/integration/test_load_lock_postgres.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from typer.testing import CliRunner

import nba_data.cli.main as cli_main
from nba_data.db.load_lock import LoadInProgressError, exclusive_load

DISPOSABLE = "postgresql+psycopg://user:pw@localhost:5432/nba_test_lock"
LOAD_COMMANDS = (
    ["backfill", "offline", "--execute-approved-backfill"],
    ["backfill", "stats", "--execute-approved-stats-backfill"],
    ["backfill", "player-stats", "--execute-approved-player-stats-backfill"],
    ["backfill", "player-postseason-stats", "--execute-approved-player-postseason-stats-backfill"],
    ["backfill", "games", "--season", "2020", "--execute-approved-games-backfill"],
    [
        "backfill",
        "current-season-identity",
        "--season",
        "2027",
        "--execute-approved-current-season-load",
    ],
    [
        "backfill",
        "current-season-games",
        "--season",
        "2027",
        "--as-of",
        "2026-11-08",
        "--execute-approved-current-season-load",
    ],
)


@pytest.mark.unit
def test_other_databases_run_without_a_lock() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with exclusive_load(engine):
            pass
    finally:
        engine.dispose()


@pytest.mark.unit
@pytest.mark.parametrize("command", LOAD_COMMANDS, ids=lambda command: command[1])
def test_every_load_stops_before_writing_when_another_load_holds_the_lock(
    command: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    disposed: list[bool] = []
    engine = SimpleNamespace(dispose=lambda: disposed.append(True))

    @contextmanager
    def held(_engine: object) -> Iterator[None]:
        raise LoadInProgressError("Another load is already writing this database")
        yield  # pragma: no cover

    def no_session(_engine: object) -> object:
        raise AssertionError("the load opened a session despite the held lock")

    settings = SimpleNamespace(
        database_url=DISPOSABLE,
        log_level="INFO",
        scraper_cache_dir=tmp_path,
        scraper_snapshot_dir=tmp_path,
    )
    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)
    monkeypatch.setattr(cli_main, "create_db_engine", lambda _settings: engine)
    monkeypatch.setattr(cli_main, "exclusive_load", held)
    monkeypatch.setattr(cli_main, "create_session_factory", no_session)

    result = CliRunner().invoke(cli_main.app, command)

    assert result.exit_code == 1, result.output
    assert "Another load is already writing this database" in result.output
    assert disposed == [True]
