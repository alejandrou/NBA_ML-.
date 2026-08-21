"""The four `*_not_synthetic` check constraints must behave on PostgreSQL.

The unit tests drive the generated condition through SQLite, which is the engine
the offline suite builds. PostgreSQL is the engine that actually holds the data,
and it is the one whose `trim`, `replace`, `substr` and `LIKE` semantics the
constraints depend on. This runs the same rule against it.

An insert can fail for reasons that have nothing to do with the rule being
tested, so every probe names the check constraint it expects and asserts against
the constraint PostgreSQL reports, rather than against "some `IntegrityError`
happened" — otherwise a unique or foreign-key violation would satisfy a
rejection test that the check constraint itself could have failed.

Environment authorization, connection lifetime, revision checking, and the
rollback that leaves the database as it was found all belong to
`tests/integration/conftest.py`.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

# The only column in the four under test that carries a global uniqueness rule,
# so the only one where a stored row can stand in the way of a probe insert.
_TEAMS_BREF_ID_UNIQUE = "uq_core_teams_bref_id"

# Values the constraints must refuse, and lookalikes they must still accept.
# `1T2M` is the one that a naive digit-stripping rule would wrongly reject.
REJECTED = ("TOT", "tot", " 5TM ", "2TM", "5TM", "10TM", "999TM", "99999999TM")
ACCEPTED = ("BOS", "CHO", "0TM", "1TM", "02TM", "TM", "1T2M", "T2M", "2MT")


@pytest.mark.integration
@pytest.mark.parametrize("value", REJECTED)
def test_postgres_refuses_a_synthetic_code_in_every_guarded_column(
    postgres_connection: Connection, value: str
) -> None:
    team_id, season_id = _seed_parents(postgres_connection)

    for statement, parameters, check_name in _inserts(
        value, team_id=team_id, season_id=season_id
    ):
        error = _integrity_error_from(postgres_connection, statement, parameters)

        assert error is not None, f"{check_name} accepted {value!r}"
        assert _violated_constraint(error) == check_name, (
            f"{value!r} was rejected by {_violated_constraint(error)!r} rather than "
            f"{check_name!r}, so this probe did not exercise the rule under test"
        )


@pytest.mark.integration
@pytest.mark.parametrize("value", ACCEPTED)
def test_postgres_still_accepts_a_code_that_is_not_a_marker(
    postgres_connection: Connection, value: str
) -> None:
    team_id, season_id = _seed_parents(postgres_connection)

    for statement, parameters, check_name in _inserts(
        value, team_id=team_id, season_id=season_id
    ):
        error = _integrity_error_from(postgres_connection, statement, parameters)
        if error is None:
            continue

        violated = _violated_constraint(error)
        assert violated != check_name, f"{check_name} wrongly rejected {value!r}"
        # A team row already owning this code is not a failure of the check —
        # that stored row had to satisfy the very constraint under test to exist,
        # which is the same conclusion the insert would have demonstrated. The
        # lane's database starts empty, so this can only be a row an earlier
        # probe in this same test inserted.
        assert violated == _TEAMS_BREF_ID_UNIQUE, (
            f"inserting {value!r} failed on {violated!r}, which is neither the "
            f"check under test nor a collision with an existing team code"
        )
        assert _team_code_is_stored(postgres_connection, value), (
            f"{violated!r} fired for {value!r} but no team row holds that code"
        )


def _inserts(
    value: str, *, team_id: int, season_id: int
) -> tuple[tuple[str, dict[str, object], str], ...]:
    """Every guarded column, each paired with the check that guards it.

    The filler code in the two `core.teams` probes is generated rather than
    hardcoded because it lands in `basketball_reference_team_id`, which is
    unique: any fixed real-looking code would collide with a row seeded
    elsewhere in the same transaction and mask the constraint this module exists
    to test.
    """

    filler = _unique_probe_code()
    return (
        (
            "insert into core.teams (basketball_reference_team_id, current_abbreviation, "
            "current_name) values (:value, :filler, 'Constraint probe')",
            {"value": value, "filler": filler},
            "ck_core_teams_bref_id_not_synthetic",
        ),
        (
            "insert into core.teams (basketball_reference_team_id, current_abbreviation, "
            "current_name) values (:filler, :value, 'Constraint probe')",
            {"value": value, "filler": filler},
            "ck_core_teams_current_abbreviation_not_synthetic",
        ),
        (
            "insert into core.team_aliases (team_id, abbreviation, name) "
            "values (:team_id, :value, 'Constraint probe')",
            {"value": value, "team_id": team_id},
            "ck_core_team_aliases_abbreviation_not_synthetic",
        ),
        (
            "insert into core.team_seasons (team_id, season_id, team_abbreviation) "
            "values (:team_id, :season_id, :value)",
            {"value": value, "team_id": team_id, "season_id": season_id},
            "ck_core_team_seasons_abbrev_not_synthetic",
        ),
    )


def _integrity_error_from(
    connection: Connection, statement: str, parameters: dict[str, object]
) -> IntegrityError | None:
    """Run one probe in a savepoint and hand back whatever it violated.

    The savepoint is rolled back before the caller asserts anything, because a
    failed statement leaves the transaction unusable until it is, and the
    assertions themselves need to query.
    """

    savepoint = connection.begin_nested()
    error: IntegrityError | None = None
    try:
        connection.execute(text(statement), parameters)
    except IntegrityError as caught:
        error = caught
    finally:
        savepoint.rollback()
    return error


def _violated_constraint(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def _team_code_is_stored(connection: Connection, value: str) -> bool:
    stored = connection.scalar(
        text(
            "select 1 from core.teams where basketball_reference_team_id = :value limit 1"
        ),
        {"value": value},
    )
    return stored is not None


def _unique_probe_code() -> str:
    """Six random letters: unique in practice, and never a synthetic marker.

    It holds no digits, so the rule's digit-stripping branch compares the whole
    six-letter code against `TM` and cannot match, and six characters can never
    be `TOT`. Six letters also cannot equal any three-letter team code.
    """

    return "".join(chr(ord("A") + byte % 26) for byte in uuid4().bytes[:6])


def _seed_parents(connection: Connection) -> tuple[int, int]:
    """Rows the foreign keys need, so a rejection can only come from the check.

    The parent carries a generated natural key because
    `0007_team_bref_id_not_null` made `basketball_reference_team_id` NOT NULL:
    without one, every probe below would fail on this insert instead of on the
    check constraint under test. The same generator serves both purposes rather
    than a second one being introduced beside it. `current_abbreviation` stays
    omitted — it is nullable and irrelevant to the parent's only job, which is
    to satisfy a foreign key.
    """

    team_id = connection.execute(
        text(
            "insert into core.teams (basketball_reference_team_id, current_name) "
            "values (:code, 'Constraint probe parent') returning id"
        ),
        {"code": _unique_probe_code()},
    ).scalar_one()
    season_id = connection.execute(
        text(
            "insert into core.seasons (season_year, league) "
            "values (-1, 'CONSTRAINT-PROBE') returning id"
        )
    ).scalar_one()
    return team_id, season_id
