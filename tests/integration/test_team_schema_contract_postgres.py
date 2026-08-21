"""`core.teams.basketball_reference_team_id` must be NOT NULL on PostgreSQL.

Revision `0007_team_bref_id_not_null` is what makes the natural key safe to
route the public teams API on: a nullable key means a team the API can never
address. This asserts that the deployed schema really refuses the null, and it
asserts it by SQLSTATE, schema, table, and column rather than by "an
`IntegrityError` was raised" — the four check constraints in
`test_synthetic_team_code_constraints_postgres.py` raise that same class, so the
weaker assertion would pass even if the NOT NULL had been dropped and something
else had objected.

It lives in its own module for the same reason: nullability is a different
contract from the synthetic-code checks, and mixing them would let one hide
behind the other.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

NOT_NULL_VIOLATION_SQLSTATE = "23502"


@pytest.mark.integration
def test_postgres_refuses_a_team_without_a_basketball_reference_id(
    postgres_connection: Connection,
) -> None:
    savepoint = postgres_connection.begin_nested()
    error: IntegrityError | None = None
    try:
        postgres_connection.execute(
            text("insert into core.teams (current_name) values ('Missing natural key')")
        )
    except IntegrityError as caught:
        error = caught
    finally:
        # Roll back so the outer transaction stays usable for the assertions and
        # for the fixture's own teardown.
        savepoint.rollback()

    assert error is not None, (
        "core.teams accepted a row with no basketball_reference_team_id, so the "
        "natural key the teams API routes on is not actually required"
    )
    diagnostic = error.orig.diag  # type: ignore[union-attr]
    assert (
        diagnostic.sqlstate,
        diagnostic.schema_name,
        diagnostic.table_name,
        diagnostic.column_name,
    ) == (NOT_NULL_VIOLATION_SQLSTATE, "core", "teams", "basketball_reference_team_id")
