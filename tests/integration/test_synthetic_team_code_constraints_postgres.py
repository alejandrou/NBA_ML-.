"""The four `*_not_synthetic` check constraints must behave on PostgreSQL.

The unit tests drive the generated condition through SQLite, which is the engine
the offline suite builds. PostgreSQL is the engine that actually holds the data,
and it is the one whose `trim`, `replace`, `substr` and `LIKE` semantics the
constraints depend on. This runs the same rule against it.

Nothing here commits: every insert happens inside a transaction that is rolled
back, so the database is left exactly as it was found.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from nba_data.config.settings import get_settings

_REQUIRE_POSTGRES_INTEGRATION_ENV = "NBA_DATA_REQUIRE_POSTGRES_INTEGRATION"
_REQUIRED_VALUES = {"1", "true", "yes", "on"}
_ALEMBIC_INI_PATH = Path(__file__).resolve().parents[2] / "alembic.ini"

# Values the constraints must refuse, and lookalikes they must still accept.
# `1T2M` is the one that a naive digit-stripping rule would wrongly reject.
REJECTED = ("TOT", "tot", " 5TM ", "2TM", "5TM", "10TM", "999TM", "99999999TM")
ACCEPTED = ("BOS", "CHO", "0TM", "1TM", "02TM", "TM", "1T2M", "T2M", "2MT")


@pytest.fixture
def connection() -> Iterator[Connection]:
    """A connection whose work is always rolled back."""

    engine = create_engine(
        get_settings().database_url,
        connect_args={"connect_timeout": 2},
        pool_pre_ping=True,
    )
    if engine.dialect.name != "postgresql":
        engine.dispose()
        pytest.fail("DATABASE_URL must configure PostgreSQL for this test", pytrace=False)

    try:
        open_connection = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        _skip_or_fail(f"PostgreSQL is unavailable: {exc}")

    try:
        _require_migration_head(open_connection)
        # Reading the revision autobegins a transaction; end it before opening
        # the explicit one whose rollback is this fixture's whole guarantee.
        open_connection.rollback()

        transaction = open_connection.begin()
        try:
            yield open_connection
        finally:
            transaction.rollback()
    finally:
        open_connection.close()
        engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("value", REJECTED)
def test_postgres_refuses_a_synthetic_code_in_every_guarded_column(
    connection: Connection, value: str
) -> None:
    for statement, parameters in _inserts(value):
        savepoint = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(text(statement), parameters)
        savepoint.rollback()


@pytest.mark.integration
@pytest.mark.parametrize("value", ACCEPTED)
def test_postgres_still_accepts_a_code_that_is_not_a_marker(
    connection: Connection, value: str
) -> None:
    team_id, season_id = _seed_parents(connection)

    for statement, parameters in _inserts(value, team_id=team_id, season_id=season_id):
        savepoint = connection.begin_nested()
        connection.execute(text(statement), parameters)
        savepoint.rollback()


def _inserts(
    value: str, *, team_id: int = -1, season_id: int = -1
) -> tuple[tuple[str, dict[str, object]], ...]:
    return (
        (
            "insert into core.teams (basketball_reference_team_id, current_abbreviation, "
            "current_name) values (:value, 'DEN', 'Constraint probe')",
            {"value": value},
        ),
        (
            "insert into core.teams (basketball_reference_team_id, current_abbreviation, "
            "current_name) values ('DEN', :value, 'Constraint probe')",
            {"value": value},
        ),
        (
            "insert into core.team_aliases (team_id, abbreviation, name) "
            "values (:team_id, :value, 'Constraint probe')",
            {"value": value, "team_id": team_id},
        ),
        (
            "insert into core.team_seasons (team_id, season_id, team_abbreviation) "
            "values (:team_id, :season_id, :value)",
            {"value": value, "team_id": team_id, "season_id": season_id},
        ),
    )


def _seed_parents(connection: Connection) -> tuple[int, int]:
    """Rows the foreign keys need, so a rejection can only come from the check."""

    team_id = connection.execute(
        text(
            "insert into core.teams (current_name) values ('Constraint probe parent') "
            "returning id"
        )
    ).scalar_one()
    season_id = connection.execute(
        text(
            "insert into core.seasons (season_year, league) "
            "values (-1, 'CONSTRAINT-PROBE') returning id"
        )
    ).scalar_one()
    return team_id, season_id


def _require_migration_head(connection: Connection) -> None:
    """These constraints only exist at the head, so anything earlier is N/A.

    A database that predates revision 0006 does not have the constraints under
    test, which is a reason to skip rather than to fail — except in CI and in
    `scripts/validate_postgres_local.py`, which both set the require-flag and so
    turn the skip into a failure.
    """

    try:
        revisions = set(
            connection.scalars(text("SELECT version_num FROM alembic_version")).all()
        )
    except SQLAlchemyError as exc:
        _skip_or_fail(f"PostgreSQL schema is not migrated: {exc}")

    heads = set(ScriptDirectory.from_config(Config(str(_ALEMBIC_INI_PATH))).get_heads())
    if revisions != heads:
        _skip_or_fail(
            f"PostgreSQL schema is at {sorted(revisions)}, "
            f"not the migration head {sorted(heads)}"
        )


def _skip_or_fail(message: str) -> NoReturn:
    if os.getenv(_REQUIRE_POSTGRES_INTEGRATION_ENV, "").strip().lower() in _REQUIRED_VALUES:
        pytest.fail(message, pytrace=False)
    pytest.skip(message)
