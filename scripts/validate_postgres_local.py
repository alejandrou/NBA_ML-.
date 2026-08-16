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

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from nba_data.config.settings import get_settings

_TEMP_DB_PREFIX = "nba_test_tmp_"
_SAFE_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_REQUIRE_ENV = "NBA_DATA_REQUIRE_POSTGRES_INTEGRATION"
_INTEGRATION_TESTS = (
    "tests/integration/test_team_season_loader_postgres.py",
    "tests/integration/test_api_postgres.py",
    "tests/integration/test_synthetic_team_code_constraints_postgres.py",
)


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

    steps = [
        ["uv", "run", "alembic", "upgrade", "head"],
        ["uv", "run", "alembic", "check"],
        # Prove the newest revision is reversible on real PostgreSQL, not only
        # that it applies. A revision that cannot be undone is a one-way door,
        # and the offline SQLite tests never exercise `downgrade` at all.
        ["uv", "run", "alembic", "downgrade", "-1"],
        ["uv", "run", "alembic", "upgrade", "head"],
        ["uv", "run", "alembic", "check"],
        *([["uv", "run", "pytest", test_path] for test_path in _INTEGRATION_TESTS]),
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
    engine = create_engine(temp_url)
    try:
        with engine.connect() as connection:
            teams = connection.execute(text("SELECT count(*) FROM core.teams")).scalar_one()
            seasons = connection.execute(text("SELECT count(*) FROM core.seasons")).scalar_one()
    finally:
        engine.dispose()

    if teams or seasons:
        raise RuntimeError(
            f"Test cleanup left {teams} team row(s) and {seasons} season row(s) behind "
            f"in the temporary database."
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
