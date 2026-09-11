"""Check the data preconditions for the unapplied migrations on one named target.

The target must be supplied explicitly so this safety check cannot silently
inspect a different database from the one an owner intends to migrate. The
check opens that target read-only where the database driver supports it and
executes count and catalog queries only; it never runs a migration, creates an
object, or changes data.

Two preconditions are assessed, each reported with its own verdict:

* ``0007_team_bref_id_not_null`` — no ``core.teams`` row may carry a NULL
  Basketball Reference team code, because the revision makes that column
  ``NOT NULL``.
* ``0008_drop_raw_schema`` — the ``raw`` schema must be absent, or hold exactly
  the three superseded tables and no rows. The revision drops those tables by
  name and then runs ``DROP SCHEMA IF EXISTS raw`` *without* ``CASCADE``, so any
  other object aborts the upgrade, a missing one aborts it too, and any row
  present is discarded by it.

Usage:
    uv run python scripts/preflight_migration_data.py \
        --database-url postgresql+psycopg://user:password@host:5432/database
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

_MIGRATION_0007 = "0007_team_bref_id_not_null"
_TARGET_COLUMN = "core.teams.basketball_reference_team_id"
_COUNT_NULL_TEAM_CODES_SQL = (
    "SELECT count(*) FROM core.teams "
    "WHERE basketball_reference_team_id IS NULL"
)

_MIGRATION_0008 = "0008_drop_raw_schema"
_RAW_SCHEMA = "raw"

#: The only relations `0008` drops. Their indexes, constraint indexes, identity
#: sequences, and TOAST tables are deliberately absent from this list: those go
#: with their parent table, and the inventory query below excludes them for the
#: same reason.
_EXPECTED_RAW_TABLES: tuple[str, ...] = ("raw_pages", "scraper_runs", "scraper_requests")

_RAW_SCHEMA_EXISTS_SQL = (
    "SELECT count(*) FROM information_schema.schemata WHERE schema_name = :schema"
)

#: Every relation standing in `raw` on its own account. The `pg_depend` filter
#: removes exactly what PostgreSQL drops alongside a parent relation — an index,
#: a serial or identity sequence, a TOAST table — so what survives it is the set
#: of objects that would still be in the schema when 0008 reaches its
#: `DROP SCHEMA`. Read from the catalog rather than assumed from a list of three
#: names, because the object this check exists to find is the one nobody
#: expected to be there.
_RAW_RELATION_INVENTORY_SQL = """
SELECT c.relname, c.relkind
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = :schema
  AND NOT EXISTS (
      SELECT 1
      FROM pg_depend AS d
      WHERE d.classid = 'pg_class'::regclass
        AND d.objid = c.oid
        AND d.deptype IN ('a', 'i')
  )
ORDER BY c.relname
"""

#: A function or procedure keeps the schema alive just as surely as a table.
_RAW_ROUTINE_INVENTORY_SQL = """
SELECT p.proname, p.prokind
FROM pg_proc AS p
JOIN pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = :schema
ORDER BY p.proname
"""

_RELKIND_LABELS = {
    "r": "table",
    "p": "partitioned table",
    "v": "view",
    "m": "materialized view",
    "f": "foreign table",
    "S": "sequence",
    "c": "composite type",
    "t": "TOAST table",
    "i": "index",
    "I": "partitioned index",
}

_PROKIND_LABELS = {
    "f": "function",
    "p": "procedure",
    "a": "aggregate",
    "w": "window function",
}

#: A target that cannot be reached must say so rather than hang. The command
#: exists to be run against remote and firewalled databases, where an unanswered
#: connection is the normal failure and silence is the worst possible report.
CONNECT_TIMEOUT_SECONDS = 10

#: PostgreSQL refuses every write on a transaction opened this way, so the
#: preflight cannot modify the target it was pointed at even if this module
#: later grew a statement that tried to.
READ_ONLY_EXECUTION_OPTIONS = {"postgresql_readonly": True}


@dataclass(frozen=True)
class PreconditionReport:
    """One migration's verdict, kept separate from every other migration's.

    Observations are what the owner is told whatever the outcome; blockers are
    the specific reasons that migration must not be applied. They stay separate
    because "raw.raw_pages has 12 rows" and "raw contains an unrecognized table"
    lead to different decisions, and collapsing them into one opaque failure
    would take that distinction away.
    """

    migration: str
    observations: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.blockers


def connect_read_only(engine):
    """Open the target the way the preflight opens it, and only that way.

    Kept as one named function so the read-only guarantee can be exercised
    against a real PostgreSQL server rather than only against a stub that would
    accept a misspelled option just as happily.
    """

    return engine.connect().execution_options(**READ_ONLY_EXECUTION_OPTIONS)


def check_0007_precondition(connection) -> PreconditionReport:
    """Every `core.teams` row must already carry a Basketball Reference code."""

    null_count = int(connection.execute(text(_COUNT_NULL_TEAM_CODES_SQL)).scalar_one())
    observations = (f"{_TARGET_COLUMN} NULL count: {null_count}",)
    if null_count == 0:
        return PreconditionReport(_MIGRATION_0007, observations)

    return PreconditionReport(
        _MIGRATION_0007,
        observations,
        (f"{null_count} row(s) have NULL {_TARGET_COLUMN}.",),
    )


def check_0008_precondition(connection) -> PreconditionReport:
    """The `raw` schema must be absent, or hold only the three empty tables."""

    schema_present = bool(
        connection.execute(text(_RAW_SCHEMA_EXISTS_SQL), {"schema": _RAW_SCHEMA}).scalar_one()
    )
    if not schema_present:
        return PreconditionReport(
            _MIGRATION_0008,
            (f"schema {_RAW_SCHEMA} is absent; the revision has nothing left to drop.",),
        )

    relations = connection.execute(
        text(_RAW_RELATION_INVENTORY_SQL), {"schema": _RAW_SCHEMA}
    ).all()
    routines = connection.execute(
        text(_RAW_ROUTINE_INVENTORY_SQL), {"schema": _RAW_SCHEMA}
    ).all()

    present_names = [str(name) for name, _ in relations]
    observations = [
        f"schema {_RAW_SCHEMA} holds {len(relations)} relation(s) and "
        f"{len(routines)} routine(s): {', '.join(present_names) or '(none)'}"
    ]

    blockers = [
        _unrecognized(_RELKIND_LABELS.get(str(kind), "object"), str(name))
        for name, kind in relations
        if str(name) not in _EXPECTED_RAW_TABLES
    ]
    blockers += [
        _unrecognized(_PROKIND_LABELS.get(str(kind), "routine"), str(name))
        for name, kind in routines
    ]

    # A partially present `raw` schema is a blocker in its own right: 0008 drops
    # all three tables by name and aborts on the first one that is not there.
    blockers += [
        f"{_RAW_SCHEMA}.{table} is missing, but {_MIGRATION_0008} drops it by name."
        for table in _EXPECTED_RAW_TABLES
        if table not in present_names
    ]

    for table in _EXPECTED_RAW_TABLES:
        if table not in present_names:
            # Counting a table the catalog says is absent would fail the whole
            # connection, turning a reportable blocker into an unassessed target.
            continue
        # The name interpolated here is one of this module's own constants,
        # filtered by the catalog read above. No caller-supplied value, and no
        # catalog-supplied name, reaches this statement.
        row_count = int(
            connection.execute(text(f"SELECT count(*) FROM {_RAW_SCHEMA}.{table}")).scalar_one()
        )
        observations.append(f"{_RAW_SCHEMA}.{table} row count: {row_count}")
        if row_count:
            blockers.append(
                f"{_RAW_SCHEMA}.{table} has {row_count} row(s); "
                f"{_MIGRATION_0008} discards them."
            )

    return PreconditionReport(_MIGRATION_0008, tuple(observations), tuple(blockers))


def _unrecognized(label: str, name: str) -> str:
    return (
        f"{_RAW_SCHEMA} contains an unrecognized {label} '{_RAW_SCHEMA}.{name}'; "
        f"DROP SCHEMA {_RAW_SCHEMA} runs without CASCADE and would abort the upgrade."
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        engine = create_engine(
            args.database_url,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        )
        try:
            with connect_read_only(engine) as connection:
                reports = (
                    check_0007_precondition(connection),
                    check_0008_precondition(connection),
                )
        finally:
            engine.dispose()
    except Exception as exc:  # noqa: BLE001 - do not expose a URL or password
        print(
            f"Migration preflight failed ({type(exc).__name__}); the target was not assessed.",
            file=sys.stderr,
        )
        return 1

    return _report(reports)


def _report(reports: tuple[PreconditionReport, ...]) -> int:
    """Print one verdict per migration, and exit nonzero if any of them blocks."""

    for report in reports:
        for observation in report.observations:
            print(f"{report.migration}: {observation}")
        if report.passed:
            print(f"Preflight passed for {report.migration}: the data precondition holds.")
            continue

        for blocker in report.blockers:
            print(f"{report.migration}: {blocker}", file=sys.stderr)
        print(f"Migration {report.migration} must not be applied.", file=sys.stderr)

    if all(report.passed for report in reports):
        return 0

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
    # back — it carries the password. The checks below read PostgreSQL schemas
    # and catalogs through a PostgreSQL-only read-only option, so another backend
    # is a mistake worth naming rather than a generic failure to connect.
    try:
        backend = make_url(args.database_url).get_backend_name()
    except ArgumentError:
        parser.error("--database-url is not a database URL SQLAlchemy can parse")
    if backend != "postgresql":
        parser.error(f"--database-url must name a PostgreSQL target, not {backend!r}")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
