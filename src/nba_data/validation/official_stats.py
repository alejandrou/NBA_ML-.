from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, func, inspect, or_, select
from sqlalchemy.orm import Session

_NON_DATA_COLUMNS = {
    "id",
    "player_team_season_id",
    "player_season_id",
    "source_team_code",
    "source_url",
    "cache_path",
    "parser_version",
    "created_at",
    "updated_at",
}
_BANNED_GENERATED_NAME_TOKENS = (
    "ovr",
    "rank",
    "ranking",
    "similar",
    "recommend",
    "ml",
    "predict",
    "prediction",
    "feature",
)


@dataclass(frozen=True)
class StatsTableSpec:
    table_name: str
    grain_column: str
    parent_table: str
    aggregate_table: bool = False

    @property
    def full_name(self) -> str:
        return f"stats.{self.table_name}"


STATS_TABLE_SPECS = (
    StatsTableSpec("player_team_season_roster", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec("player_team_season_totals", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec("player_team_season_per_game", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec("player_team_season_per_minute", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec("player_team_season_per_poss", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec("player_team_season_advanced", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec("player_team_season_shooting", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec(
        "player_team_season_adj_shooting",
        "player_team_season_id",
        "player_team_seasons",
    ),
    StatsTableSpec("player_team_season_pbp", "player_team_season_id", "player_team_seasons"),
    StatsTableSpec("player_season_totals", "player_season_id", "player_seasons", True),
    StatsTableSpec("player_season_per_game", "player_season_id", "player_seasons", True),
    StatsTableSpec("player_season_per_minute", "player_season_id", "player_seasons", True),
    StatsTableSpec("player_season_per_poss", "player_season_id", "player_seasons", True),
    StatsTableSpec("player_season_advanced", "player_season_id", "player_seasons", True),
    StatsTableSpec("player_season_shooting", "player_season_id", "player_seasons", True),
    StatsTableSpec("player_season_adj_shooting", "player_season_id", "player_seasons", True),
    StatsTableSpec("player_season_pbp", "player_season_id", "player_seasons", True),
)


@dataclass(frozen=True)
class OfficialStatsValidationIssue:
    code: str
    message: str
    context: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class OfficialStatsValidationReport:
    passed: bool
    table_counts: Mapping[str, int]
    backfill_summary: Mapping[str, object]
    issues: tuple[OfficialStatsValidationIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "table_counts": dict(self.table_counts),
            "backfill_summary": dict(self.backfill_summary),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_official_stats(
    session: Session,
    stats_backfill_report: Mapping[str, Any] | None = None,
) -> OfficialStatsValidationReport:
    """Validate the official Phase 4E stats schema without mutating it."""

    bind = session.get_bind()
    inspector = inspect(bind)
    metadata = MetaData()
    stats_schema_tables = set(inspector.get_table_names(schema="stats"))

    reflected_tables: dict[str, Table] = {}
    table_counts: dict[str, int] = {}
    issues: list[OfficialStatsValidationIssue] = []

    for spec in STATS_TABLE_SPECS:
        if spec.table_name not in stats_schema_tables:
            table_counts[spec.full_name] = 0
            issues.append(
                OfficialStatsValidationIssue(
                    code="missing_stats_table",
                    message=f"Required stats table {spec.full_name} is missing.",
                    context={"table": spec.full_name},
                )
            )
            continue
        table = Table(spec.table_name, metadata, schema="stats", autoload_with=bind)
        reflected_tables[spec.table_name] = table
        table_counts[spec.full_name] = session.scalar(select(func.count()).select_from(table)) or 0

    core_tables = {
        name: Table(name, metadata, schema="core", autoload_with=bind)
        for name in ("teams", "team_seasons", "players", "seasons", "player_seasons", "player_team_seasons")
    }

    issues.extend(_duplicate_issues(session, reflected_tables))
    issues.extend(_fk_grain_issues(session, reflected_tables, core_tables))
    issues.extend(_tot_placement_issues(session, reflected_tables, core_tables))
    issues.extend(_row_content_issues(session, reflected_tables))
    issues.extend(_generated_schema_issues(inspector))

    backfill_summary = _extract_backfill_summary(stats_backfill_report)
    issues.extend(_backfill_report_issues(table_counts, backfill_summary, stats_backfill_report))

    return OfficialStatsValidationReport(
        passed=not issues,
        table_counts=table_counts,
        backfill_summary=backfill_summary,
        issues=tuple(issues),
    )


def _duplicate_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    issues: list[OfficialStatsValidationIssue] = []
    for spec in STATS_TABLE_SPECS:
        table = reflected_tables.get(spec.table_name)
        if table is None:
            continue
        grain = table.c[spec.grain_column]
        statement = (
            select(grain, func.count().label("row_count"))
            .select_from(table)
            .group_by(grain)
            .having(func.count() > 1)
        )
        rows = [
            {spec.grain_column: row[0], "row_count": int(row.row_count)}
            for row in session.execute(statement)
        ]
        if rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="duplicate_logical_rows",
                    message=f"Duplicate logical rows found in stats.{spec.table_name}.",
                    context={"table": spec.full_name, "examples": rows[:10]},
                )
            )
    return issues


def _fk_grain_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
    core_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    player_team_seasons = core_tables["player_team_seasons"]
    player_seasons = core_tables["player_seasons"]
    team_seasons = core_tables["team_seasons"]
    players = core_tables["players"]
    seasons = core_tables["seasons"]

    issues: list[OfficialStatsValidationIssue] = []
    for spec in STATS_TABLE_SPECS:
        table = reflected_tables.get(spec.table_name)
        if table is None:
            continue
        grain = table.c[spec.grain_column]

        if spec.aggregate_table:
            orphan_stmt = (
                select(grain)
                .select_from(table)
                .outerjoin(player_seasons, grain == player_seasons.c.id)
                .where(player_seasons.c.id.is_(None))
            )
            invalid_stmt = (
                select(grain)
                .select_from(table)
                .join(player_seasons, grain == player_seasons.c.id)
                .outerjoin(players, player_seasons.c.player_id == players.c.id)
                .outerjoin(seasons, player_seasons.c.season_id == seasons.c.id)
                .where(or_(players.c.id.is_(None), seasons.c.id.is_(None)))
            )
        else:
            orphan_stmt = (
                select(grain)
                .select_from(table)
                .outerjoin(player_team_seasons, grain == player_team_seasons.c.id)
                .where(player_team_seasons.c.id.is_(None))
            )
            invalid_stmt = (
                select(grain)
                .select_from(table)
                .join(player_team_seasons, grain == player_team_seasons.c.id)
                .outerjoin(player_seasons, player_team_seasons.c.player_season_id == player_seasons.c.id)
                .outerjoin(team_seasons, player_team_seasons.c.team_season_id == team_seasons.c.id)
                .where(or_(player_seasons.c.id.is_(None), team_seasons.c.id.is_(None)))
            )

        orphan_rows = [row[0] for row in session.execute(orphan_stmt)]
        if orphan_rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="orphan_fk_grain",
                    message=f"Orphan FK grains found in stats.{spec.table_name}.",
                    context={"table": spec.full_name, "grains": orphan_rows[:10]},
                )
            )

        invalid_rows = [row[0] for row in session.execute(invalid_stmt)]
        if invalid_rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="invalid_core_grain_chain",
                    message=f"Invalid core grain chains found in stats.{spec.table_name}.",
                    context={"table": spec.full_name, "grains": invalid_rows[:10]},
                )
            )
    return issues


def _tot_placement_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
    core_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    player_team_seasons = core_tables["player_team_seasons"]
    player_seasons = core_tables["player_seasons"]
    team_seasons = core_tables["team_seasons"]
    teams = core_tables["teams"]

    issues: list[OfficialStatsValidationIssue] = []
    for spec in STATS_TABLE_SPECS:
        table = reflected_tables.get(spec.table_name)
        if table is None:
            continue
        grain = table.c[spec.grain_column]

        if spec.aggregate_table:
            statement = (
                select(grain, func.count(func.distinct(player_team_seasons.c.id)).label("stint_count"))
                .select_from(table)
                .join(player_seasons, grain == player_seasons.c.id)
                .outerjoin(player_team_seasons, player_team_seasons.c.player_season_id == player_seasons.c.id)
                .group_by(grain)
                .having(func.count(func.distinct(player_team_seasons.c.id)) <= 1)
            )
            rows = [
                {spec.grain_column: row[0], "stint_count": int(row.stint_count)}
                for row in session.execute(statement)
            ]
            if rows:
                issues.append(
                    OfficialStatsValidationIssue(
                        code="aggregate_row_not_multi_stint",
                        message=(
                            f"Aggregate rows in stats.{spec.table_name} require multi-stint player seasons."
                        ),
                        context={"table": spec.full_name, "examples": rows[:10]},
                    )
                )
            continue

        statement = (
            select(
                grain,
                team_seasons.c.team_abbreviation,
                teams.c.basketball_reference_team_id,
                teams.c.current_abbreviation,
            )
            .select_from(table)
            .join(player_team_seasons, grain == player_team_seasons.c.id)
            .join(team_seasons, player_team_seasons.c.team_season_id == team_seasons.c.id)
            .join(teams, team_seasons.c.team_id == teams.c.id)
            .where(
                or_(
                    team_seasons.c.team_abbreviation == "TOT",
                    teams.c.basketball_reference_team_id == "TOT",
                    teams.c.current_abbreviation == "TOT",
                )
            )
        )
        rows = [
            {
                spec.grain_column: row[0],
                "team_abbreviation": row.team_abbreviation,
                "basketball_reference_team_id": row.basketball_reference_team_id,
                "current_abbreviation": row.current_abbreviation,
            }
            for row in session.execute(statement)
        ]
        if rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="tot_in_team_stint_table",
                    message=f"Team-stint rows in stats.{spec.table_name} incorrectly join TOT.",
                    context={"table": spec.full_name, "examples": rows[:10]},
                )
            )
    return issues


def _row_content_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    issues: list[OfficialStatsValidationIssue] = []
    for spec in STATS_TABLE_SPECS:
        table = reflected_tables.get(spec.table_name)
        if table is None:
            continue

        data_columns = [column for column in table.columns if column.name not in _NON_DATA_COLUMNS]
        if not data_columns:
            continue

        null_examples: list[dict[str, object]] = []
        numeric_examples: list[dict[str, object]] = []
        null_count = 0
        numeric_count = 0

        for row in session.execute(select(table)).mappings():
            mapping = dict(row)
            data_values = {column.name: mapping.get(column.name) for column in data_columns}
            if all(value is None for value in data_values.values()):
                null_count += 1
                if len(null_examples) < 10:
                    null_examples.append({spec.grain_column: mapping.get(spec.grain_column)})

            violations = _numeric_violations(data_values)
            if violations:
                numeric_count += 1
                if len(numeric_examples) < 10:
                    numeric_examples.append(
                        {
                            spec.grain_column: mapping.get(spec.grain_column),
                            "violations": violations,
                        }
                    )

        if null_count:
            issues.append(
                OfficialStatsValidationIssue(
                    code="all_stat_columns_null",
                    message=f"Rows in stats.{spec.table_name} have all stat columns null.",
                    context={
                        "table": spec.full_name,
                        "row_count": null_count,
                        "examples": null_examples,
                    },
                )
            )
        if numeric_count:
            issues.append(
                OfficialStatsValidationIssue(
                    code="impossible_numeric_values",
                    message=f"Rows in stats.{spec.table_name} have impossible numeric values.",
                    context={
                        "table": spec.full_name,
                        "row_count": numeric_count,
                        "examples": numeric_examples,
                    },
                )
            )
    return issues


def _numeric_violations(data_values: Mapping[str, object]) -> list[str]:
    violations: list[str] = []
    games_played = _as_number(data_values.get("g"))
    games_started = _as_number(data_values.get("gs"))

    for column_name, value in data_values.items():
        number = _as_number(value)
        if number is None:
            continue

        if isinstance(value, int) and value < 0:
            violations.append(f"{column_name} is negative")

        if column_name == "age" and not _is_between(number, 15, 60):
            violations.append("age outside 15-60")
        elif column_name == "weight" and not _is_between(number, 100, 500):
            violations.append("weight outside 100-500")
        elif column_name == "g" and not _is_between(number, 0, 110):
            violations.append("g outside 0-110")
        elif column_name == "gs" and not _is_between(number, 0, 110):
            violations.append("gs outside 0-110")
        elif column_name == "mp" and not _is_between(number, 0, 5000):
            violations.append("mp outside 0-5000")
        elif column_name == "mp_per_game" and not _is_between(number, 0, 60):
            violations.append("mp_per_game outside 0-60")
        elif column_name == "avg_dist" and not _is_between(number, 0, 94):
            violations.append("avg_dist outside 0-94")
        elif column_name in {"ortg", "drtg"} and not _is_between(number, 0, 300):
            violations.append(f"{column_name} outside 0-300")
        elif _is_percentage_like(column_name):
            upper = 2 if column_name.startswith("adj_") else 1
            if not _is_between(number, 0, upper):
                violations.append(f"{column_name} outside 0-{upper}")

    if games_played is not None and games_started is not None and games_started > games_played:
        violations.append("gs greater than g")
    return violations


def _generated_schema_issues(inspector: Any) -> list[OfficialStatsValidationIssue]:
    table_names = inspector.get_table_names(schema="stats")
    offenders: list[dict[str, object]] = []
    for table_name in table_names:
        banned_tokens = _matched_tokens(table_name)
        if banned_tokens:
            offenders.append(
                {
                    "object_type": "table",
                    "table": f"stats.{table_name}",
                    "tokens": banned_tokens,
                }
            )
        for column in inspector.get_columns(table_name, schema="stats"):
            column_name = str(column["name"])
            banned_tokens = _matched_tokens(column_name)
            if banned_tokens:
                offenders.append(
                    {
                        "object_type": "column",
                        "table": f"stats.{table_name}",
                        "column": column_name,
                        "tokens": banned_tokens,
                    }
                )

    if not offenders:
        return []
    return [
        OfficialStatsValidationIssue(
            code="generated_metric_schema_name",
            message="Generated-output names were found in the stats schema.",
            context={"objects": offenders[:25]},
        )
    ]


def _backfill_report_issues(
    table_counts: Mapping[str, int],
    backfill_summary: Mapping[str, object],
    stats_backfill_report: Mapping[str, Any] | None,
) -> list[OfficialStatsValidationIssue]:
    if stats_backfill_report is None:
        return []

    issues: list[OfficialStatsValidationIssue] = []
    persisted_total_rows = sum(table_counts.values())
    loaded_rows = backfill_summary.get("stats_loaded_rows")
    if loaded_rows is None:
        issues.append(
            OfficialStatsValidationIssue(
                code="stats_backfill_report_missing_field",
                message="Stats backfill report is missing stats_loaded_rows.",
            )
        )
    elif loaded_rows != persisted_total_rows:
        issues.append(
            OfficialStatsValidationIssue(
                code="backfill_row_mismatch",
                message=(
                    f"Persisted stats rows total {persisted_total_rows}; "
                    f"stats backfill report loaded {loaded_rows} rows."
                ),
                context={
                    "persisted_total_rows": persisted_total_rows,
                    "stats_loaded_rows": loaded_rows,
                },
            )
        )

    failure_fields = {
        "processing_failed_sources": backfill_summary.get("processing_failed_sources"),
        "stats_failed_rows": backfill_summary.get("stats_failed_rows"),
        "stats_quarantined_rows": backfill_summary.get("stats_quarantined_rows"),
    }
    nonzero_failures = {
        key: value for key, value in failure_fields.items() if isinstance(value, int | float) and value != 0
    }
    if nonzero_failures:
        issues.append(
            OfficialStatsValidationIssue(
                code="backfill_failures_present",
                message="Stats backfill report contains nonzero processing, load, or quarantine failures.",
                context=nonzero_failures,
            )
        )
    return issues


def _extract_backfill_summary(stats_backfill_report: Mapping[str, Any] | None) -> dict[str, object]:
    if stats_backfill_report is None:
        return {}
    return {
        "selected_sources": stats_backfill_report.get("selected_sources"),
        "processed_sources": stats_backfill_report.get("processed_sources"),
        "processing_failed_sources": stats_backfill_report.get("processing_failed_sources"),
        "stats_loaded_rows": stats_backfill_report.get("stats_loaded_rows"),
        "stats_skipped_rows": stats_backfill_report.get("stats_skipped_rows"),
        "stats_failed_rows": stats_backfill_report.get("stats_failed_rows"),
        "stats_quarantined_rows": stats_backfill_report.get("stats_quarantined_rows"),
    }


def _matched_tokens(name: str) -> tuple[str, ...]:
    lowered = name.lower()
    return tuple(token for token in _BANNED_GENERATED_NAME_TOKENS if token in lowered)


def _is_percentage_like(column_name: str) -> bool:
    return "pct" in column_name


def _is_between(value: Decimal, minimum: int | float, maximum: int | float) -> bool:
    return Decimal(str(minimum)) <= value <= Decimal(str(maximum))


def _as_number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    return None


def _json_safe_value(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


__all__ = [
    "OfficialStatsValidationIssue",
    "OfficialStatsValidationReport",
    "STATS_TABLE_SPECS",
    "StatsTableSpec",
    "validate_official_stats",
]
