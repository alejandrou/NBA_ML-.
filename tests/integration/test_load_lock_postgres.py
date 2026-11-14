"""One load at a time (R-02) and locale-independent list order (R-07), on PostgreSQL."""

from __future__ import annotations

import time

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from nba_data.db.load_lock import LOAD_LOCK_KEY, LoadInProgressError, exclusive_load
from nba_data.db.repositories.queries.players import list_players

pytestmark = pytest.mark.integration


def _lock_holders(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted "
                    "AND ((classid::bigint << 32) | objid::bigint) = :key"
                ),
                {"key": LOAD_LOCK_KEY},
            )
        )


def test_a_second_load_fails_at_once_while_the_first_holds_the_lock(
    postgres_engine: Engine,
) -> None:
    with exclusive_load(postgres_engine):
        assert _lock_holders(postgres_engine) == 1
        started = time.monotonic()
        with (
            pytest.raises(LoadInProgressError, match="already writing"),
            exclusive_load(postgres_engine),
        ):
            pass  # pragma: no cover
        assert time.monotonic() - started < 5

    assert _lock_holders(postgres_engine) == 0
    with exclusive_load(postgres_engine):
        pass


def test_a_failed_load_releases_the_lock(postgres_engine: Engine) -> None:
    with pytest.raises(RuntimeError, match="load failed"), exclusive_load(postgres_engine):
        raise RuntimeError("load failed")

    assert _lock_holders(postgres_engine) == 0


def test_the_lock_holds_no_open_transaction_while_the_load_runs(postgres_engine: Engine) -> None:
    """An idle-in-transaction holder would pin a snapshot for the whole load."""
    with exclusive_load(postgres_engine), postgres_engine.connect() as observer:
        states = observer.scalars(
            text(
                "SELECT a.state FROM pg_locks l JOIN pg_stat_activity a USING (pid) "
                "WHERE l.locktype = 'advisory' "
                "AND ((l.classid::bigint << 32) | l.objid::bigint) = :key"
            ),
            {"key": LOAD_LOCK_KEY},
        ).all()
    assert states == ["idle"]


def test_players_are_listed_in_icu_root_order(postgres_connection: Connection) -> None:
    """glibc's en_US ignores spaces ("Alan Anderson" before "Al Horford"); ICU does not."""
    names = ["Zeta Zed", "Alex Len", "Álex Abrines", "Alan Anderson", "Al Horford"]
    for index, name in enumerate(names):
        postgres_connection.execute(
            text(
                "INSERT INTO core.players (basketball_reference_player_id, full_name) "
                "VALUES (:player_id, :name)"
            ),
            {"player_id": f"zzorder{index:02d}", "name": name},
        )
    session = Session(bind=postgres_connection, join_transaction_mode="create_savepoint")
    try:
        listed = [player.full_name for player in list_players(session, offset=0, limit=10)]
    finally:
        session.close()

    assert listed == ["Al Horford", "Alan Anderson", "Álex Abrines", "Alex Len", "Zeta Zed"]
