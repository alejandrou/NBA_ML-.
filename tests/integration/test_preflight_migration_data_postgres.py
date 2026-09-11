"""The preflight must work, and must be unable to write, on real PostgreSQL.

`tests/unit/test_preflight_migration_data.py` drives the same entry point
through a stub. A stub accepts a misspelled execution option, a query naming a
column that does not exist, and a catalog filter that would keep every index in
the schema, so it can prove the branching and the exit codes but not the three
things the preflight is trusted for: that its literal statements run against the
real catalog, that they see what PostgreSQL actually holds, and that the
connection it opens genuinely refuses writes. All three are asserted here
against the server itself.

The preflight opens its own Engine from a URL rather than borrowing a fixture's
connection — that is its real shape as an operator command — so these tests give
it the disposable database's URL and let it connect for itself. They read counts
and catalogs and write nothing, so the lane's empty-database guarantee is
untouched.
"""

from __future__ import annotations

import pytest
from scripts import preflight_migration_data
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

# Imported for its import side effect: the mapped-table comparison below is only
# complete once every model module has been imported.
from nba_data.db import models as _models  # noqa: F401
from nba_data.db.base import Base

#: `read_only_sql_transaction` — what PostgreSQL raises when a read-only
#: transaction is asked to modify anything.
READ_ONLY_VIOLATION_SQLSTATE = "25006"

CORE_SCHEMA = "core"


@pytest.mark.integration
def test_preflight_passes_against_a_database_at_the_migration_head(
    postgres_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both literal checks resolve and report on the deployed schema.

    The lane's database is empty and at head, so the honest answers are zero
    NULL team codes and an absent `raw` schema, and the honest exit code is
    zero. A statement that failed to resolve — a renamed column, a catalog view
    spelled wrong — would surface here as the caught-and-reported failure path
    instead.
    """

    exit_code = preflight_migration_data.main(["--database-url", _url_of(postgres_engine)])

    captured = capsys.readouterr()
    assert exit_code == 0, captured.err
    assert f"{preflight_migration_data._TARGET_COLUMN} NULL count: 0" in captured.out
    assert f"Preflight passed for {preflight_migration_data._MIGRATION_0007}" in captured.out
    assert "schema raw is absent" in captured.out
    assert f"Preflight passed for {preflight_migration_data._MIGRATION_0008}" in captured.out


@pytest.mark.integration
def test_the_0008_check_runs_on_a_connection_that_cannot_write(
    postgres_engine: Engine,
) -> None:
    """The catalog reads work under the read-only option, not merely beside it.

    `SET TRANSACTION READ ONLY` is not a permission model — it is a property of
    the transaction the check's own statements run in. Calling the check through
    the preflight's own connection helper is what proves those statements
    succeed inside it, rather than only outside it in some other test's
    connection.
    """

    engine = create_engine(_url_of(postgres_engine))
    try:
        with preflight_migration_data.connect_read_only(engine) as connection:
            report = preflight_migration_data.check_0008_precondition(connection)
    finally:
        engine.dispose()

    assert report.migration == preflight_migration_data._MIGRATION_0008
    assert report.passed, report.blockers
    assert any("is absent" in observation for observation in report.observations)


@pytest.mark.integration
def test_the_raw_inventory_query_ignores_indexes_and_owned_sequences(
    postgres_engine: Engine,
) -> None:
    """The dependency filter is checked against a schema that really has both.

    The lane's `raw` schema is gone at head, so the query would return an empty
    list there whether its `pg_depend` filter worked or not. Pointing the same
    statement at `core` — which carries primary-key indexes, unique indexes, and
    an identity sequence per table — is what proves the filter keeps exactly the
    relations that stand on their own. Without it, every index in `raw` would be
    reported to an owner as an unrecognized object.
    """

    mapped = {table.name for table in Base.metadata.sorted_tables if table.schema == CORE_SCHEMA}
    assert mapped, "no core tables are mapped, so this test would pass vacuously"

    engine = create_engine(_url_of(postgres_engine))
    try:
        with preflight_migration_data.connect_read_only(engine) as connection:
            rows = connection.execute(
                text(preflight_migration_data._RAW_RELATION_INVENTORY_SQL),
                {"schema": CORE_SCHEMA},
            ).all()
    finally:
        engine.dispose()

    assert {name for name, _ in rows} == mapped
    assert {kind for _, kind in rows} == {"r"}


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
