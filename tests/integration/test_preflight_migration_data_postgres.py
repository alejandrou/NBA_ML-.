"""The `0007` preflight must work, and must be unable to write, on PostgreSQL.

`tests/unit/test_preflight_migration_data.py` drives the same entry point
through a stub. A stub accepts a misspelled execution option and a query naming
a column that does not exist, so it can prove the branching and the exit codes
but not the two things the preflight is trusted for: that its literal statement
runs against the real schema, and that the connection it opens genuinely refuses
writes. Both are asserted here against the server itself.

The preflight opens its own Engine from a URL rather than borrowing a fixture's
connection — that is its real shape as an operator command — so these tests give
it the disposable database's URL and let it connect for itself. It reads one
count and writes nothing, so the lane's empty-database guarantee is untouched.
"""

from __future__ import annotations

import pytest
from scripts import preflight_migration_data
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

#: `read_only_sql_transaction` — what PostgreSQL raises when a read-only
#: transaction is asked to modify anything.
READ_ONLY_VIOLATION_SQLSTATE = "25006"


@pytest.mark.integration
def test_preflight_passes_against_a_database_with_no_null_team_codes(
    postgres_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    """The literal statement resolves and counts on the deployed schema.

    The lane's database is empty and at head, so the honest answer is zero and
    the honest exit code is zero. A count that failed to resolve — a renamed
    column, a missing schema — would surface here as the caught-and-reported
    failure path instead.
    """

    exit_code = preflight_migration_data.main(["--database-url", _url_of(postgres_engine)])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert f"{preflight_migration_data._TARGET_COLUMN} NULL count: 0" in captured.out
    assert "Preflight passed" in captured.out


@pytest.mark.integration
def test_the_preflight_connection_cannot_write_to_the_target(postgres_engine: Engine) -> None:
    """The read-only option is enforced by the server, not merely requested.

    This inserts through the preflight's own connection helper because the
    guarantee being tested belongs to that connection. A write refused here is a
    write refused for anything the preflight might ever run against a database
    an owner is about to migrate.
    """

    engine = create_engine(_url_of(postgres_engine))
    try:
        with (
            preflight_migration_data.connect_read_only(engine) as connection,
            pytest.raises(DBAPIError) as caught,
        ):
            connection.execute(
                text(
                    "insert into core.teams "
                    "(basketball_reference_team_id, current_name) "
                    "values ('PFL', 'Preflight must never write this')"
                )
            )
    finally:
        engine.dispose()

    diagnostic = caught.value.orig.diag  # type: ignore[union-attr]
    assert diagnostic.sqlstate == READ_ONLY_VIOLATION_SQLSTATE, (
        f"the insert was refused with SQLSTATE {diagnostic.sqlstate}, not by the "
        f"read-only transaction, so the preflight's write protection is unproven"
    )


def _url_of(engine: Engine) -> str:
    """The disposable database's URL, password included, as the CLI takes it."""

    return engine.url.render_as_string(hide_password=False)
