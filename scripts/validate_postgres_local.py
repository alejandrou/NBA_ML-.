"""Run the PostgreSQL integration tests against a disposable, isolated database.

The configured DATABASE_URL (`nba` by default) is typically a developer's real
local database and must never be seeded, migrated in place, or dropped by an
automated test run. This script instead creates a uniquely named scratch
database on the same PostgreSQL server, points a *child process* environment
at it, migrates and tests that database only, and always drops it afterward.

Requires the configured PostgreSQL role to have CREATEDB privilege. Uses a
plain TCP connection (via the already-configured DATABASE_URL host/port), not
`docker exec`, so it works the same way regardless of how PostgreSQL is run.

Usage:
    uv run python scripts/validate_postgres_local.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from nba_data.config.settings import get_settings

# Imported for its import side effect: the empty check below derives its table
# list from the shared metadata, which is only complete once every model module
# has been imported.
from nba_data.db import models as _models  # noqa: F401
from nba_data.db.base import Base

_TEMP_DB_PREFIX = "nba_test_tmp_"
_CORE_SCHEMA = "core"
_SAFE_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_REQUIRE_ENV = "NBA_DATA_REQUIRE_POSTGRES_INTEGRATION"
# The tests refuse to connect without this, whatever DATABASE_URL says. Setting
# it is only safe here because the database it will name is one this script
# generated moments ago and drops before it returns.
_TEST_DATABASE_ENV = "NBA_DATA_TEST_DATABASE"


def main() -> int:
    source_url = make_url(get_settings().database_url)
    if source_url.get_backend_name() != "postgresql":
        print("DATABASE_URL must configure PostgreSQL.", file=sys.stderr)
        return 1

    temp_db_name = f"{_TEMP_DB_PREFIX}{uuid4().hex[:16]}"
    if not _SAFE_NAME_RE.fullmatch(temp_db_name):
        raise AssertionError(f"generated database name is unsafe: {temp_db_name!r}")
    if temp_db_name == source_url.database:
        raise AssertionError("generated database name collided with the configured database")

    admin_engine = create_engine(source_url, isolation_level="AUTOCOMMIT")
    try:
        print(f"Creating temporary database {temp_db_name!r}...")
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{temp_db_name}"'))
    except Exception:
        admin_engine.dispose()
        raise

    try:
        return _migrate_and_test(source_url, temp_db_name)
    finally:
        print(f"Dropping temporary database {temp_db_name!r}...")
        _drop_database(admin_engine, temp_db_name)
        admin_engine.dispose()


def _migrate_and_test(source_url, temp_db_name: str) -> int:
    temp_url = source_url.set(database=temp_db_name)
    child_env = dict(os.environ)
    child_env["DATABASE_URL"] = temp_url.render_as_string(hide_password=False)
    child_env[_REQUIRE_ENV] = "1"
    child_env[_TEST_DATABASE_ENV] = "1"

    steps = [
        ["uv", "run", "alembic", "upgrade", "head"],
        ["uv", "run", "alembic", "check"],
        # Prove the newest revision is reversible on real PostgreSQL, not only
        # that it applies. A revision that cannot be undone is a one-way door,
        # and the offline SQLite tests never exercise `downgrade` at all.
        ["uv", "run", "alembic", "downgrade", "-1"],
        ["uv", "run", "alembic", "upgrade", "head"],
        ["uv", "run", "alembic", "check"],
        # The whole directory, not a list of modules: a new integration test is
        # then covered the moment it is written, rather than whenever someone
        # remembers to add it here.
        ["uv", "run", "pytest", "-ra", "tests/integration"],
    ]
    for command in steps:
        print(f"$ {' '.join(command)}")
        result = subprocess.run(command, env=child_env, check=False)
        if result.returncode != 0:
            return result.returncode

    _verify_empty(temp_url)
    print(f"PostgreSQL validation passed against {temp_db_name!r}.")
    return 0


def _verify_empty(temp_url) -> None:
    """Confirm from outside the test process that nothing was committed.

    The integration session checks this too, but from inside the process whose
    transaction handling is the thing in doubt. This is the independent look at
    the terminal state, and it covers every mapped `core` table rather than the
    two that happened to be seeded when it was written.
    """

    engine = create_engine(temp_url)
    try:
        with engine.connect() as connection:
            populated = {
                table.fullname: count
                for table in Base.metadata.sorted_tables
                if table.schema == _CORE_SCHEMA
                and (count := connection.execute(select(func.count()).select_from(table)).scalar_one())
            }
    finally:
        engine.dispose()

    if populated:
        left_behind = ", ".join(f"{name}={count}" for name, count in sorted(populated.items()))
        raise RuntimeError(
            f"Test cleanup left rows behind in the temporary database: {left_behind}"
        )


def _drop_database(admin_engine, name: str) -> None:
    if not name.startswith(_TEMP_DB_PREFIX):
        raise AssertionError(f"refusing to drop a database outside the temp prefix: {name!r}")

    with admin_engine.connect() as connection:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))


if __name__ == "__main__":
    raise SystemExit(main())
