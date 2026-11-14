"""Loads refresh planner statistics (DATABASE_AUDIT_2026-11-10, H-10)."""

from __future__ import annotations

import time

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from nba_data.db.session import analyze_database

pytestmark = pytest.mark.integration


def test_analyze_records_statistics_for_the_loaded_schemas(postgres_engine: Engine) -> None:
    assert analyze_database(postgres_engine) is True

    with postgres_engine.connect() as connection:
        never_analyzed = connection.scalar(
            text(
                "SELECT count(*) FROM pg_stat_user_tables "
                "WHERE schemaname IN ('core', 'stats') "
                "AND last_analyze IS NULL AND last_autoanalyze IS NULL"
            )
        )
    assert never_analyzed == 0


def _never_analyzed(engine: Engine, schema: str) -> int:
    with engine.connect() as connection:
        return int(
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_user_tables WHERE schemaname = :schema "
                    "AND last_analyze IS NULL AND last_autoanalyze IS NULL"
                ),
                {"schema": schema},
            )
        )


def test_analyze_touches_only_the_requested_schemas(postgres_engine: Engine) -> None:
    before = _never_analyzed(postgres_engine, "ml")

    assert analyze_database(postgres_engine, ("core",)) is True

    assert _never_analyzed(postgres_engine, "core") == 0
    assert _never_analyzed(postgres_engine, "ml") == before


def test_a_held_lock_fails_analyze_quickly_instead_of_waiting(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as holder:
        # SHARE UPDATE EXCLUSIVE is what ANALYZE itself takes, so it conflicts.
        holder.execute(text("LOCK TABLE core.seasons IN SHARE UPDATE EXCLUSIVE MODE"))
        started = time.monotonic()
        with pytest.raises(OperationalError, match="lock timeout"):
            analyze_database(postgres_engine, ("core",), lock_timeout_seconds=0.2)
        assert time.monotonic() - started < 5
        holder.rollback()
