"""Check the data precondition for migration 0007 on one named target.

The target must be supplied explicitly so this safety check cannot silently
inspect a different database from the one an owner intends to migrate. The
check opens that target read-only where the database driver supports it and
executes one count query; it never runs a migration or changes data.

Usage:
    uv run python scripts/preflight_migration_data.py \
        --database-url postgresql+psycopg://user:password@host:5432/database
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

_MIGRATION_NAME = "0007_team_bref_id_not_null"
_TARGET_COLUMN = "core.teams.basketball_reference_team_id"
_COUNT_NULL_TEAM_CODES_SQL = (
    "SELECT count(*) FROM core.teams "
    "WHERE basketball_reference_team_id IS NULL"
)

#: A target that cannot be reached must say so rather than hang. The command
#: exists to be run against remote and firewalled databases, where an unanswered
#: connection is the normal failure and silence is the worst possible report.
CONNECT_TIMEOUT_SECONDS = 10

#: PostgreSQL refuses every write on a transaction opened this way, so the
#: preflight cannot modify the target it was pointed at even if this module
#: later grew a statement that tried to.
READ_ONLY_EXECUTION_OPTIONS = {"postgresql_readonly": True}


def connect_read_only(engine):
    """Open the target the way the preflight opens it, and only that way.

    Kept as one named function so the read-only guarantee can be exercised
    against a real PostgreSQL server rather than only against a stub that would
    accept a misspelled option just as happily.
    """

    return engine.connect().execution_options(**READ_ONLY_EXECUTION_OPTIONS)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        engine = create_engine(
            args.database_url,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        )
        try:
            with connect_read_only(engine) as connection:
                null_count = int(
                    connection.execute(text(_COUNT_NULL_TEAM_CODES_SQL)).scalar_one()
                )
        finally:
            engine.dispose()
    except Exception as exc:  # noqa: BLE001 - do not expose a URL or password
        print(
            f"Migration preflight failed ({type(exc).__name__}); the target was not assessed.",
            file=sys.stderr,
        )
        return 1

    print(f"{_TARGET_COLUMN} NULL count: {null_count}")
    if null_count == 0:
        print(f"Preflight passed for {_MIGRATION_NAME}: the data precondition holds.")
        return 0

    print(
        f"Migration {_MIGRATION_NAME} must not be applied: "
        f"{null_count} row(s) have NULL {_TARGET_COLUMN}.",
        file=sys.stderr,
    )
    print("Remediation is a separate decision for the user.", file=sys.stderr)
    return 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="Explicit database URL for the target being assessed.",
    )
    args = parser.parse_args(argv)
    if not args.database_url.strip():
        # `required=True` is satisfied by an empty string, which is exactly what
        # `--database-url "$DATABASE_URL"` sends when that variable is unset.
        # Assessing an unnamed target is the mistake this check exists to stop.
        parser.error("--database-url must name the target database; it cannot be empty")

    # Rejected here, before any connection, and reported without echoing the URL
    # back — it carries the password. The count below reads a PostgreSQL schema
    # through a PostgreSQL-only read-only option, so another backend is a
    # mistake worth naming rather than a generic failure to connect.
    try:
        backend = make_url(args.database_url).get_backend_name()
    except ArgumentError:
        parser.error("--database-url is not a database URL SQLAlchemy can parse")
    if backend != "postgresql":
        parser.error(f"--database-url must name a PostgreSQL target, not {backend!r}")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
