"""F4E-024 rehearsal: rebuild the player-page stats archive at parser v4.

Runs the whole documented backfill sequence against a uniquely named scratch
database on the same PostgreSQL server, captures the grain evidence the card
asks for, and drops the scratch database in a ``finally`` path whatever the
outcome. The configured database (``nba`` by default) is never written to: it is
used only as the admin connection that issues ``CREATE DATABASE`` and
``DROP DATABASE``, and every child process is pointed at the scratch database
through ``DATABASE_URL``.

This mirrors the isolation pattern already established in
``scripts/validate_postgres_local.py``. Every backfill step below is a
documented CLI command; the script exists for the isolation and the evidence
capture, not to replace the runbook.

Usage:
    uv run python scripts/dev/rehearse_player_page_rebuild.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from nba_data.config.settings import get_settings

_TEMP_DB_PREFIX = "nba_f4e024_tmp_"
_SAFE_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_REPORTS = Path("reports/F4E-024")

# Every command the rehearsal runs, with its exit code, recorded into the
# evidence file so the handover procedure quotes measured results.
_STEP_RESULTS: list[dict[str, object]] = []

# The buckets the archive audit decomposes the 634-row gap into. The 9
# postseason-only seasons are the fifth bucket and are expected to stay empty.
_MARKER_SEASON = ("jonesbo02", 2008)
_DNP_SEASON = ("milleol01", 2004)
_POSTSEASON_ONLY = [
    ("adamsja01", 2020),
    ("hollajo02", 2016),
    ("jeffrda01", 2023),
    ("jonesdw02", 2013),
    ("lawsoty01", 2018),
    ("mcgratr01", 2013),
    ("thomptr01", 2023),
    ("vildolu01", 2022),
    ("wrighdo01", 2016),
]

_REGULAR_AGGREGATE_TABLES = [
    "player_season_adj_shooting",
    "player_season_advanced",
    "player_season_pbp",
    "player_season_per_game",
    "player_season_per_minute",
    "player_season_per_poss",
    "player_season_shooting",
    "player_season_totals",
]
_POSTSEASON_AGGREGATE_TABLES = [
    table.replace("player_season_", "player_postseason_") for table in _REGULAR_AGGREGATE_TABLES
]

_GRAIN_SQL = """
select p.basketball_reference_player_id, s.season_year
from stats.{table} t
join core.player_seasons ps on ps.id = t.player_season_id
join core.players p on p.id = ps.player_id
join core.seasons s on s.id = ps.season_id
"""

_NAMED_SEASON_SQL = """
select count(*) from stats.{table} t
join core.player_seasons ps on ps.id = t.player_season_id
join core.players p on p.id = ps.player_id
join core.seasons s on s.id = ps.season_id
where p.basketball_reference_player_id = :pid and s.season_year = :year
"""


def main() -> int:
    _REPORTS.mkdir(parents=True, exist_ok=True)
    source_url = make_url(get_settings().database_url)
    if source_url.get_backend_name() != "postgresql":
        print("DATABASE_URL must configure PostgreSQL.", file=sys.stderr)
        return 1

    temp_db_name = f"{_TEMP_DB_PREFIX}{uuid4().hex[:16]}"
    if not _SAFE_NAME_RE.fullmatch(temp_db_name):
        raise AssertionError(f"generated database name is unsafe: {temp_db_name!r}")
    if temp_db_name == source_url.database:
        raise AssertionError("generated database name collided with the configured database")

    print(f"Configured database: {source_url.database!r} (never written to)")
    print(f"Scratch database:    {temp_db_name!r}")

    admin_engine = create_engine(source_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{temp_db_name}"'))
    except Exception:
        admin_engine.dispose()
        raise

    temp_url = source_url.set(database=temp_db_name)
    exit_code = 1
    try:
        exit_code = _rehearse(source_url, temp_url)
    finally:
        try:
            _collect_evidence(temp_url)
        except Exception as exc:  # evidence is best effort; the drop is not
            print(f"Evidence collection failed: {exc}", file=sys.stderr)
        print(f"Dropping scratch database {temp_db_name!r}...")
        _drop_database(admin_engine, temp_db_name)
        admin_engine.dispose()
    return exit_code


def _child_env(source_url, temp_url) -> dict[str, str]:
    """Point a child process at the scratch database, and prove it is not `nba`."""

    if temp_url.database == source_url.database:
        raise AssertionError("refusing to run a backfill against the configured database")
    if not str(temp_url.database).startswith(_TEMP_DB_PREFIX):
        raise AssertionError(
            f"refusing to run a backfill outside the temp prefix: {temp_url.database!r}"
        )
    child_env = dict(os.environ)
    child_env["DATABASE_URL"] = temp_url.render_as_string(hide_password=False)
    return child_env


def _rehearse(source_url, temp_url) -> int:
    child_env = _child_env(source_url, temp_url)
    steps: list[list[str]] = [
        ["uv", "run", "alembic", "upgrade", "head"],
        ["uv", "run", "alembic", "check"],
        [
            "uv", "run", "nba-data", "backfill", "offline",
            "--execute-approved-backfill",
            "--output", str(_REPORTS / "offline_backfill.json"),
        ],
        [
            "uv", "run", "nba-data", "backfill", "stats",
            "--execute-approved-stats-backfill",
            "--output", str(_REPORTS / "team_stats_backfill.json"),
        ],
        [
            "uv", "run", "nba-data", "backfill", "player-stats",
            "--execute-approved-player-stats-backfill",
            "--output", str(_REPORTS / "player_stats_backfill.json"),
        ],
        [
            "uv", "run", "nba-data", "backfill", "player-postseason-stats",
            "--execute-approved-player-postseason-stats-backfill",
            "--output", str(_REPORTS / "player_postseason_stats_backfill.json"),
        ],
    ]
    for command in steps:
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        print(f"\n[{stamp}] $ {' '.join(command)}", flush=True)
        result = subprocess.run(command, env=child_env, check=False)
        _STEP_RESULTS.append({"command": " ".join(command), "exit_code": result.returncode})
        if result.returncode != 0:
            print(f"Step failed with exit code {result.returncode}.", file=sys.stderr)
            return result.returncode

    return _validate(child_env)


def _validate(child_env: dict[str, str]) -> int:
    """Run the two validators against the scratch database, capturing their JSON.

    Their exit codes are returned, but the caller still collects grain evidence
    afterwards: a validation failure is a finding to read, not a reason to lose
    the measurements that explain it.
    """

    checks: list[tuple[str, list[str]]] = [
        (
            "validate_offline_database",
            [
                "uv", "run", "nba-data", "validate", "offline-database",
                "--backfill-report", str(_REPORTS / "offline_backfill.json"),
            ],
        ),
        (
            "validate_official_stats",
            [
                "uv", "run", "nba-data", "validate", "official-stats",
                "--team-stats-report", str(_REPORTS / "team_stats_backfill.json"),
                "--player-stats-report", str(_REPORTS / "player_stats_backfill.json"),
                "--player-postseason-stats-report",
                str(_REPORTS / "player_postseason_stats_backfill.json"),
                "--coverage-artifact", str(_REPORTS / "stats_coverage.json"),
                "--coverage-cache-root", str(get_settings().scraper_cache_dir),
            ],
        ),
    ]
    # The coverage artifact is database-free, so it is built concurrently with
    # the backfills to save an hour of wall clock. Give it a bounded chance to
    # land rather than failing the comparison on a race.
    artifact = _REPORTS / "stats_coverage.json"
    deadline = time.monotonic() + 3600
    while not artifact.exists() and time.monotonic() < deadline:
        time.sleep(30)

    worst = 0
    for name, command in checks:
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        print(f"\n[{stamp}] $ {' '.join(command)}", flush=True)
        result = subprocess.run(command, env=child_env, check=False, capture_output=True, text=True)
        log = _REPORTS / f"{name}.log"
        log.write_text(
            f"$ {' '.join(command)}\nexit={result.returncode}\n\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
        print(f"exit={result.returncode} -> {log}", flush=True)
        _STEP_RESULTS.append({"command": " ".join(command), "exit_code": result.returncode})
        worst = worst or result.returncode
    return worst


def _collect_evidence(temp_url) -> None:
    engine = create_engine(temp_url)
    evidence: dict[str, object] = {
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "steps": list(_STEP_RESULTS),
    }
    try:
        with engine.connect() as connection:
            evidence["core_counts"] = {
                name: connection.execute(text(f"select count(*) from core.{name}")).scalar_one()
                for name in ("players", "seasons", "player_seasons", "player_team_seasons")
            }

            stats_tables = (
                connection.execute(
                    text(
                        "select table_name from information_schema.tables "
                        "where table_schema = 'stats' order by table_name"
                    )
                )
                .scalars()
                .all()
            )
            evidence["stats_table_count"] = len(stats_tables)
            per_table: dict[str, dict[str, int]] = {}
            for table in stats_tables:
                rows = connection.execute(
                    text(f"select parser_version, count(*) from stats.{table} group by 1 order by 1")
                ).all()
                per_table[table] = {version: count for version, count in rows}
            evidence["lineage_by_table"] = per_table
            evidence["distinct_parser_versions"] = sorted(
                {version for counts in per_table.values() for version in counts}
            )

            evidence["grain_counts"] = {
                "regular_aggregate_distinct_player_seasons": connection.execute(
                    text("select count(distinct player_season_id) from stats.player_season_totals")
                ).scalar_one(),
                "postseason_aggregate_distinct_player_seasons": connection.execute(
                    text(
                        "select count(distinct player_season_id) "
                        "from stats.player_postseason_totals"
                    )
                ).scalar_one(),
                "postseason_stint_distinct_player_team_seasons": connection.execute(
                    text(
                        "select count(distinct player_team_season_id) "
                        "from stats.player_team_postseason_totals"
                    )
                ).scalar_one(),
                "team_season_stint_distinct_player_team_seasons": connection.execute(
                    text(
                        "select count(distinct player_team_season_id) "
                        "from stats.player_team_season_totals"
                    )
                ).scalar_one(),
            }

            after_keys = {
                (player_id, year)
                for player_id, year in connection.execute(
                    text(_GRAIN_SQL.format(table="player_season_totals"))
                ).all()
            }
            _write_keys(_REPORTS / "scratch_regular_grain_after.txt", after_keys)
            evidence["recovery"] = _reconcile(after_keys)

            evidence["named_seasons"] = {
                "jonesbo02_2008": _rows_per_table(
                    connection, _REGULAR_AGGREGATE_TABLES, *_MARKER_SEASON
                ),
                "milleol01_2004": _rows_per_table(
                    connection, _REGULAR_AGGREGATE_TABLES, *_DNP_SEASON
                ),
            }
            evidence["milleol01_2004_totals"] = connection.execute(
                text(
                    "select t.g, t.pts from stats.player_season_totals t "
                    "join core.player_seasons ps on ps.id = t.player_season_id "
                    "join core.players p on p.id = ps.player_id "
                    "join core.seasons s on s.id = ps.season_id "
                    "where p.basketball_reference_player_id = :pid and s.season_year = :year"
                ),
                {"pid": _DNP_SEASON[0], "year": _DNP_SEASON[1]},
            ).all()

            evidence["postseason_only_seasons"] = {
                f"{player_id}_{year}": {
                    "regular_aggregate_rows": _rows_per_table(
                        connection, _REGULAR_AGGREGATE_TABLES, player_id, year
                    ),
                    "postseason_aggregate_rows": _rows_per_table(
                        connection, _POSTSEASON_AGGREGATE_TABLES, player_id, year
                    ),
                }
                for player_id, year in _POSTSEASON_ONLY
            }
    finally:
        engine.dispose()

    out = _REPORTS / "rehearsal_evidence.json"
    out.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")
    highlights = {
        key: evidence[key]
        for key in ("core_counts", "grain_counts", "distinct_parser_versions", "recovery")
        if key in evidence
    }
    print(json.dumps(highlights, indent=2, default=str))


def _rows_per_table(connection, tables: list[str], player_id: str, season_year: int) -> dict[str, int]:
    return {
        table: connection.execute(
            text(_NAMED_SEASON_SQL.format(table=table)),
            {"pid": player_id, "year": season_year},
        ).scalar_one()
        for table in tables
    }


def _write_keys(path: Path, keys: set[tuple[str, int]]) -> None:
    path.write_text(
        "".join(f"{player_id}|{year}\n" for player_id, year in sorted(keys)), encoding="utf-8"
    )


def _reconcile(after_keys: set[tuple[str, int]]) -> dict[str, object]:
    """Decompose the recovery against the archive audit's buckets."""

    before_path = _REPORTS / "nba_regular_grain_before.txt"
    if not before_path.exists():
        return {"error": f"missing baseline capture at {before_path}"}
    before_keys = {
        (player_id, int(year))
        for player_id, year in (
            line.split("|", 1)
            for line in before_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }

    recovered = sorted(after_keys - before_keys)
    lost = sorted(before_keys - after_keys)
    buckets: dict[str, list[str]] = {
        "season_2000": [],
        "short_player_id": [],
        "marker_5tm": [],
        "dnp_placeholder": [],
        "unclassified": [],
    }
    for player_id, year in recovered:
        if (player_id, year) == _MARKER_SEASON:
            buckets["marker_5tm"].append(f"{player_id} {year}")
        elif (player_id, year) == _DNP_SEASON:
            buckets["dnp_placeholder"].append(f"{player_id} {year}")
        elif year == 2000:
            buckets["season_2000"].append(f"{player_id} {year}")
        elif len(player_id) <= 7:
            buckets["short_player_id"].append(f"{player_id} {year}")
        else:
            buckets["unclassified"].append(f"{player_id} {year}")

    return {
        "before_distinct_player_seasons": len(before_keys),
        "after_distinct_player_seasons": len(after_keys),
        "recovered": len(recovered),
        "lost": len(lost),
        "lost_keys": [f"{player_id} {year}" for player_id, year in lost],
        "buckets": {name: len(items) for name, items in buckets.items()},
        "unclassified_keys": buckets["unclassified"],
    }


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
