from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path, PureWindowsPath
from typing import Any, Literal, TypeGuard

from sqlalchemy import MetaData, Table, func, inspect, or_, select
from sqlalchemy.orm import Session

from nba_data.db.repositories.queries.seasons import NBA_LEAGUE, get_season_years
from nba_data.domain.team_codes import (
    is_aggregate_only_team_code,
    is_multi_team_marker,
    is_synthetic_team_code,
)
from nba_data.scraping.player_page_cache import PlayerCacheRootNotFoundError
from nba_data.validation.parser_contracts import (
    PARSER_CONTRACTS_BY_IDENTIFIER,
    ParserProducer,
    classify_parser_version,
)
from nba_data.validation.stats_coverage import (
    StatsCoverageEntry,
    StatsCoverageSchemaError,
    StatsCoverageShapeError,
    compute_cache_fingerprint,
    parse_stats_coverage_artifact,
)

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
_POSTSEASON_MARKERS = ("postseason", "playoff", "_post")
_ADVANCED_PERCENTAGE_COLUMNS = {
    "orb_pct",
    "drb_pct",
    "trb_pct",
    "ast_pct",
    "stl_pct",
    "blk_pct",
    "tov_pct",
    "usg_pct",
}
_PBP_POSITION_COLUMNS = {"pct_pg", "pct_sg", "pct_sf", "pct_pf", "pct_c"}
_TWO_POINT_PERCENTAGE_COLUMNS = {"efg_pct", "ts_pct"}
_SPECIAL_RATE_RANGES = {
    "fg3a_per_fga_pct": (0, 1),
    "fta_per_fga_pct": (0, 10),
    "adj_efg_pct": (0, 350),
    "adj_fg3a_per_fga_pct": (0, 3000),
    "adj_fta_per_fga_pct": (0, 3000),
}
_SIGNED_NUMERIC_COLUMNS = {
    "per",
    "ows",
    "dws",
    "ws",
    "ws_per_48",
    "obpm",
    "dbpm",
    "bpm",
    "vorp",
    "fg_pts_added",
    "ts_pts_added",
    "on_court_plus_minus",
    "net_plus_minus",
}


@dataclass(frozen=True)
class StatsTableSpec:
    table_name: str
    grain_column: str
    parent_table: str
    season_type: Literal["regular", "postseason"]
    family: Literal["team_stint", "aggregate"]

    @property
    def full_name(self) -> str:
        return f"stats.{self.table_name}"

    @property
    def requires_source_team_code(self) -> bool:
        return self.family == "aggregate"

    @property
    def expected_parser_producer(self) -> ParserProducer:
        """The `parser_contracts` producer that must have written this table.

        Postseason tables — aggregate and team-stint alike — are written by the
        postseason player-page backfill. Regular-season aggregate tables are
        written by the regular player-page backfill; regular-season team-stint
        tables are written by the team-season backfill.
        """

        if self.season_type == "postseason":
            return "player_page_postseason"
        if self.family == "aggregate":
            return "player_page_regular"
        return "team_season"


REGULAR_TEAM_STINT_TABLE_SPECS = (
    StatsTableSpec("player_team_season_roster", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_totals", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_per_game", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_per_minute", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_per_poss", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_advanced", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_shooting", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_adj_shooting", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
    StatsTableSpec("player_team_season_pbp", "player_team_season_id", "player_team_seasons", "regular", "team_stint"),
)
REGULAR_AGGREGATE_TABLE_SPECS = (
    StatsTableSpec("player_season_totals", "player_season_id", "player_seasons", "regular", "aggregate"),
    StatsTableSpec("player_season_per_game", "player_season_id", "player_seasons", "regular", "aggregate"),
    StatsTableSpec("player_season_per_minute", "player_season_id", "player_seasons", "regular", "aggregate"),
    StatsTableSpec("player_season_per_poss", "player_season_id", "player_seasons", "regular", "aggregate"),
    StatsTableSpec("player_season_advanced", "player_season_id", "player_seasons", "regular", "aggregate"),
    StatsTableSpec("player_season_shooting", "player_season_id", "player_seasons", "regular", "aggregate"),
    StatsTableSpec("player_season_adj_shooting", "player_season_id", "player_seasons", "regular", "aggregate"),
    StatsTableSpec("player_season_pbp", "player_season_id", "player_seasons", "regular", "aggregate"),
)
POSTSEASON_AGGREGATE_TABLE_SPECS = (
    StatsTableSpec("player_postseason_totals", "player_season_id", "player_seasons", "postseason", "aggregate"),
    StatsTableSpec("player_postseason_per_game", "player_season_id", "player_seasons", "postseason", "aggregate"),
    StatsTableSpec("player_postseason_per_minute", "player_season_id", "player_seasons", "postseason", "aggregate"),
    StatsTableSpec("player_postseason_per_poss", "player_season_id", "player_seasons", "postseason", "aggregate"),
    StatsTableSpec("player_postseason_advanced", "player_season_id", "player_seasons", "postseason", "aggregate"),
    StatsTableSpec("player_postseason_shooting", "player_season_id", "player_seasons", "postseason", "aggregate"),
    StatsTableSpec("player_postseason_adj_shooting", "player_season_id", "player_seasons", "postseason", "aggregate"),
    StatsTableSpec("player_postseason_pbp", "player_season_id", "player_seasons", "postseason", "aggregate"),
)
POSTSEASON_TEAM_STINT_TABLE_SPECS = (
    StatsTableSpec("player_team_postseason_totals", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
    StatsTableSpec("player_team_postseason_per_game", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
    StatsTableSpec("player_team_postseason_per_minute", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
    StatsTableSpec("player_team_postseason_per_poss", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
    StatsTableSpec("player_team_postseason_advanced", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
    StatsTableSpec("player_team_postseason_shooting", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
    StatsTableSpec("player_team_postseason_adj_shooting", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
    StatsTableSpec("player_team_postseason_pbp", "player_team_season_id", "player_team_seasons", "postseason", "team_stint"),
)
STATS_TABLE_SPECS = (
    *REGULAR_TEAM_STINT_TABLE_SPECS,
    *REGULAR_AGGREGATE_TABLE_SPECS,
    *POSTSEASON_AGGREGATE_TABLE_SPECS,
    *POSTSEASON_TEAM_STINT_TABLE_SPECS,
)

StatsBackfillReportKind = Literal[
    "team_stats",
    "player_stats",
    "player_postseason_stats",
]
STATS_BACKFILL_REPORT_KINDS: tuple[StatsBackfillReportKind, ...] = (
    "team_stats",
    "player_stats",
    "player_postseason_stats",
)
_REPORT_KIND_ALIASES: dict[str, StatsBackfillReportKind] = {
    "team": "team_stats",
    "team_stats": "team_stats",
    "team_stats_report": "team_stats",
    "player": "player_stats",
    "player_stats": "player_stats",
    "player_stats_report": "player_stats",
    "player_postseason": "player_postseason_stats",
    "player_postseason_stats": "player_postseason_stats",
    "player_postseason_stats_report": "player_postseason_stats",
}
_REPORT_LABELS: dict[StatsBackfillReportKind, str] = {
    "team_stats": "team stats",
    "player_stats": "player stats",
    "player_postseason_stats": "player postseason stats",
}
_REPORT_ROW_COUNT_FIELDS: dict[StatsBackfillReportKind, tuple[str, ...]] = {
    "team_stats": ("stats_loaded_rows",),
    "player_stats": ("rows_loaded_or_updated",),
    "player_postseason_stats": (
        "aggregate_rows_loaded_or_updated",
        "team_rows_loaded_or_updated",
    ),
}
_REPORT_FAILURE_FIELDS: dict[StatsBackfillReportKind, dict[str, tuple[str, ...]]] = {
    "team_stats": {
        "entries_failed": ("entries_failed",),
        "rows_failed": ("rows_failed",),
        "processing_failed_sources": ("processing_failed_sources",),
        "stats_failed_rows": ("stats_failed_rows",),
        "rows_quarantined": ("stats_quarantined_rows",),
    },
    "player_stats": {
        "entries_failed": ("entries_failed",),
        "rows_failed": ("rows_failed",),
        "rows_unresolved": ("unresolved_players_or_seasons",),
    },
    "player_postseason_stats": {
        "entries_failed": ("entries_failed",),
        "rows_failed": ("rows_failed",),
        "rows_unresolved": ("unresolved_players_or_seasons_or_team_stints",),
    },
}
# Diagnostic producer fields the summary carries through without gating the
# result: out-of-scope rows are cache seasons the archive does not load.
_PLAYER_REPORT_METADATA_FIELDS = (
    "cache_root",
    "discovery_status",
    "out_of_scope_players_or_seasons",
    "out_of_scope_players_or_seasons_or_team_stints",
    "out_of_scope_reason_counts",
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
            "context": _json_safe_mapping(self.context),
        }


@dataclass(frozen=True)
class OfficialStatsValidationReport:
    passed: bool
    table_counts: Mapping[str, int]
    validation_summary: Mapping[str, int]
    backfill_summary: Mapping[str, object]
    issues: tuple[OfficialStatsValidationIssue, ...]
    coverage_summary: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "table_counts": dict(self.table_counts),
            "validation_summary": dict(self.validation_summary),
            "backfill_summary": _json_safe_mapping(self.backfill_summary),
            "issues": [issue.to_dict() for issue in self.issues],
            "coverage_summary": _json_safe_mapping(self.coverage_summary),
        }


def validate_official_stats(
    session: Session,
    stats_backfill_reports: Mapping[str, Any] | None = None,
    *,
    coverage_artifact: Mapping[str, object] | None = None,
    coverage_cache_root: str | Path | None = None,
) -> OfficialStatsValidationReport:
    """Validate the official Phase 4E stats schema without mutating it.

    `coverage_artifact` is the JSON-decoded F4E-017 stats-coverage artifact
    (see `nba_data.validation.stats_coverage`); when supplied, persisted
    natural keys are diffed against it so a missing or unexpected row fails
    validation even when aggregate row counts reconcile. Omitting it does not
    skip the rest of validation — it emits `coverage_artifact_missing` instead,
    because a permanent invariant must not silently pass when its oracle is
    absent. `coverage_cache_root`, if given, additionally verifies the
    artifact's cache fingerprint against the live cache before comparing keys.
    """

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
                    context={"table": spec.full_name, "count": 1},
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
    core_team_aliases = (
        Table("team_aliases", metadata, schema="core", autoload_with=bind)
        if "team_aliases" in inspector.get_table_names(schema="core")
        else None
    )

    issues.extend(_schema_requirement_issues(inspector, reflected_tables))
    issues.extend(_duplicate_issues(session, reflected_tables))
    issues.extend(_fk_grain_issues(session, reflected_tables, core_tables))
    issues.extend(_core_synthetic_code_issues(session, core_tables, core_team_aliases))
    issues.extend(_team_stint_synthetic_code_issues(session, reflected_tables, core_tables))
    issues.extend(_aggregate_source_team_code_issues(session, reflected_tables, core_tables, core_team_aliases))
    issues.extend(_regular_postseason_separation_issues(session, reflected_tables))
    issues.extend(_parser_version_issues(session, reflected_tables))
    issues.extend(_row_content_issues(session, reflected_tables))
    issues.extend(_generated_schema_issues(inspector))

    backfill_summary = _extract_backfill_summary(stats_backfill_reports)
    issues.extend(_backfill_report_issues(table_counts, backfill_summary, stats_backfill_reports))

    coverage_issues, coverage_summary = _coverage_issues(
        session,
        reflected_tables,
        core_tables,
        coverage_artifact=coverage_artifact,
        coverage_cache_root=coverage_cache_root,
    )
    issues.extend(coverage_issues)

    validation_summary = _build_validation_summary(issues)

    return OfficialStatsValidationReport(
        passed=not issues,
        table_counts=table_counts,
        validation_summary=validation_summary,
        backfill_summary=backfill_summary,
        issues=tuple(issues),
        coverage_summary=coverage_summary,
    )


def _schema_requirement_issues(
    inspector: Any,
    reflected_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    issues: list[OfficialStatsValidationIssue] = []
    validate_fk_constraints = getattr(getattr(inspector, "bind", None), "dialect", None) is not None and (
        inspector.bind.dialect.name != "sqlite"
    )
    for spec in STATS_TABLE_SPECS:
        table = reflected_tables.get(spec.table_name)
        if table is None:
            continue

        column_names = {column.name for column in table.columns}
        if spec.grain_column not in column_names:
            issues.append(
                OfficialStatsValidationIssue(
                    code="missing_required_column",
                    message=f"stats.{spec.table_name} is missing grain column {spec.grain_column}.",
                    context={"table": spec.full_name, "column": spec.grain_column, "count": 1},
                )
            )

        has_source_team_code = "source_team_code" in column_names
        if spec.requires_source_team_code and not has_source_team_code:
            issues.append(
                OfficialStatsValidationIssue(
                    code="missing_required_column",
                    message=f"stats.{spec.table_name} is missing source_team_code metadata.",
                    context={"table": spec.full_name, "column": "source_team_code", "count": 1},
                )
            )
        if not spec.requires_source_team_code and has_source_team_code:
            issues.append(
                OfficialStatsValidationIssue(
                    code="unexpected_source_team_code_column",
                    message=f"stats.{spec.table_name} must not carry source_team_code.",
                    context={"table": spec.full_name, "column": "source_team_code", "count": 1},
                )
            )

        if validate_fk_constraints:
            foreign_keys = inspector.get_foreign_keys(spec.table_name, schema="stats")
            matching_fk = any(
                tuple(fk.get("constrained_columns") or ()) == (spec.grain_column,)
                and fk.get("referred_schema") == "core"
                and fk.get("referred_table") == spec.parent_table
                and tuple(fk.get("referred_columns") or ()) == ("id",)
                for fk in foreign_keys
            )
            if not matching_fk:
                issues.append(
                    OfficialStatsValidationIssue(
                        code="invalid_fk_constraint",
                        message=(
                            f"stats.{spec.table_name} must FK {spec.grain_column} "
                            f"to core.{spec.parent_table}.id."
                        ),
                        context={"table": spec.full_name, "column": spec.grain_column, "count": 1},
                    )
                )

        unique_constraints = inspector.get_unique_constraints(spec.table_name, schema="stats")
        unique_indexes = inspector.get_indexes(spec.table_name, schema="stats")
        has_unique_grain = any(
            tuple(constraint.get("column_names") or ()) == (spec.grain_column,)
            for constraint in unique_constraints
        ) or any(
            index.get("unique") and tuple(index.get("column_names") or ()) == (spec.grain_column,)
            for index in unique_indexes
        )
        if not has_unique_grain:
            issues.append(
                OfficialStatsValidationIssue(
                    code="missing_unique_grain_constraint",
                    message=f"stats.{spec.table_name} must enforce unique grain on {spec.grain_column}.",
                    context={"table": spec.full_name, "column": spec.grain_column, "count": 1},
                )
            )
    return issues


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
                    context={
                        "table": spec.full_name,
                        "count": sum(entry["row_count"] - 1 for entry in rows),
                        "examples": rows[:10],
                    },
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
        if table is None or spec.grain_column not in table.c:
            continue
        grain = table.c[spec.grain_column]

        if spec.family == "aggregate":
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
                    context={"table": spec.full_name, "count": len(orphan_rows), "grains": orphan_rows[:10]},
                )
            )

        invalid_rows = [row[0] for row in session.execute(invalid_stmt)]
        if invalid_rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="invalid_core_grain_chain",
                    message=f"Invalid core grain chains found in stats.{spec.table_name}.",
                    context={"table": spec.full_name, "count": len(invalid_rows), "grains": invalid_rows[:10]},
                )
            )
    return issues


def _core_synthetic_code_issues(
    session: Session,
    core_tables: Mapping[str, Table],
    core_team_aliases: Table | None,
) -> list[OfficialStatsValidationIssue]:
    teams = core_tables["teams"]
    team_seasons = core_tables["team_seasons"]
    player_team_seasons = core_tables["player_team_seasons"]

    issues: list[OfficialStatsValidationIssue] = []

    # The marker set is open-ended, so it cannot be pushed into a SQL `IN`.
    # `core` identity tables are small enough to classify in Python instead.
    team_rows = [
        row
        for row in session.execute(
            select(
                teams.c.id,
                teams.c.basketball_reference_team_id,
                teams.c.current_abbreviation,
            )
        )
        if is_synthetic_team_code(row.basketball_reference_team_id)
        or is_synthetic_team_code(row.current_abbreviation)
    ]
    if team_rows:
        issues.append(
            OfficialStatsValidationIssue(
                code="synthetic_code_in_core_teams",
                message="Synthetic team codes were found in core.teams.",
                context={
                    "table": "core.teams",
                    "count": len(team_rows),
                    "examples": [
                        {
                            "id": row.id,
                            "basketball_reference_team_id": row.basketball_reference_team_id,
                            "current_abbreviation": row.current_abbreviation,
                        }
                        for row in team_rows[:10]
                    ],
                },
            )
        )

    if core_team_aliases is not None:
        alias_rows = [
            row
            for row in session.execute(
                select(core_team_aliases.c.id, core_team_aliases.c.abbreviation)
            )
            if is_synthetic_team_code(row.abbreviation)
        ]
        if alias_rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="synthetic_code_in_core_team_aliases",
                    message="Synthetic team codes were found in core.team_aliases.",
                    context={
                        "table": "core.team_aliases",
                        "count": len(alias_rows),
                        "examples": [{"id": row.id, "abbreviation": row.abbreviation} for row in alias_rows[:10]],
                    },
                )
            )

    team_season_rows = [
        row
        for row in session.execute(select(team_seasons.c.id, team_seasons.c.team_abbreviation))
        if is_synthetic_team_code(row.team_abbreviation)
    ]
    if team_season_rows:
        issues.append(
            OfficialStatsValidationIssue(
                code="synthetic_code_in_core_team_seasons",
                message="Synthetic team codes were found in core.team_seasons.",
                context={
                    "table": "core.team_seasons",
                    "count": len(team_season_rows),
                    "examples": [
                        {"id": row.id, "team_abbreviation": row.team_abbreviation}
                        for row in team_season_rows[:10]
                    ],
                },
            )
        )

    pts_rows = [
        row
        for row in session.execute(
            select(
                player_team_seasons.c.id,
                team_seasons.c.team_abbreviation,
            )
            .select_from(player_team_seasons)
            .join(team_seasons, player_team_seasons.c.team_season_id == team_seasons.c.id)
        )
        if is_synthetic_team_code(row.team_abbreviation)
    ]
    if pts_rows:
        issues.append(
            OfficialStatsValidationIssue(
                code="synthetic_code_in_core_player_team_seasons",
                message="Synthetic team codes were found in core.player_team_seasons.",
                context={
                    "table": "core.player_team_seasons",
                    "count": len(pts_rows),
                    "examples": [
                        {"id": row.id, "team_abbreviation": row.team_abbreviation}
                        for row in pts_rows[:10]
                    ],
                },
            )
        )

    return issues


def _team_stint_synthetic_code_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
    core_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    player_team_seasons = core_tables["player_team_seasons"]
    team_seasons = core_tables["team_seasons"]
    teams = core_tables["teams"]

    # Classify the core chain once, in Python, because the marker set is
    # open-ended; the per-table scans then filter on plain grain ids.
    synthetic_grains = {
        row.id: {
            "team_abbreviation": row.team_abbreviation,
            "basketball_reference_team_id": row.basketball_reference_team_id,
            "current_abbreviation": row.current_abbreviation,
        }
        for row in session.execute(
            select(
                player_team_seasons.c.id,
                team_seasons.c.team_abbreviation,
                teams.c.basketball_reference_team_id,
                teams.c.current_abbreviation,
            )
            .select_from(player_team_seasons)
            .join(team_seasons, player_team_seasons.c.team_season_id == team_seasons.c.id)
            .join(teams, team_seasons.c.team_id == teams.c.id)
        )
        if is_synthetic_team_code(row.team_abbreviation)
        or is_synthetic_team_code(row.basketball_reference_team_id)
        or is_synthetic_team_code(row.current_abbreviation)
    }

    issues: list[OfficialStatsValidationIssue] = []
    if not synthetic_grains:
        return issues

    for spec in STATS_TABLE_SPECS:
        if spec.family != "team_stint":
            continue
        table = reflected_tables.get(spec.table_name)
        if table is None or spec.grain_column not in table.c:
            continue
        grain = table.c[spec.grain_column]
        rows = [
            {spec.grain_column: value, **synthetic_grains[value]}
            for value in session.scalars(
                select(grain).select_from(table).where(grain.in_(synthetic_grains))
            )
        ]
        if rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="synthetic_code_in_team_stint_stats",
                    message=f"Synthetic team codes were found in stats.{spec.table_name}.",
                    context={
                        "table": spec.full_name,
                        "count": len(rows),
                        "examples": rows[:10],
                    },
                )
            )
    return issues


def _aggregate_source_team_code_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
    core_tables: Mapping[str, Table],
    core_team_aliases: Table | None,
) -> list[OfficialStatsValidationIssue]:
    teams = core_tables["teams"]
    team_seasons = core_tables["team_seasons"]

    known_real_codes = {
        str(value).upper()
        for value in session.scalars(select(teams.c.basketball_reference_team_id)).all()
        if value is not None
    }
    known_real_codes.update(
        str(value).upper()
        for value in session.scalars(select(teams.c.current_abbreviation)).all()
        if value is not None
    )
    known_real_codes.update(
        str(value).upper()
        for value in session.scalars(select(team_seasons.c.team_abbreviation)).all()
        if value is not None
    )
    if core_team_aliases is not None and "abbreviation" in core_team_aliases.c:
        known_real_codes.update(
            str(value).upper()
            for value in session.scalars(select(core_team_aliases.c.abbreviation)).all()
            if value is not None
        )

    issues: list[OfficialStatsValidationIssue] = []
    for spec in STATS_TABLE_SPECS:
        if spec.family != "aggregate":
            continue
        table = reflected_tables.get(spec.table_name)
        if table is None or "source_team_code" not in table.c:
            continue

        grain = table.c[spec.grain_column]
        source_team_code = table.c.source_team_code
        rows = list(session.execute(select(grain, source_team_code).select_from(table)))

        missing_rows = [
            {spec.grain_column: row[0]}
            for row in rows
            if row[1] is None or not str(row[1]).strip()
        ]
        if missing_rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="missing_source_team_code_value",
                    message=f"Aggregate rows in stats.{spec.table_name} are missing source_team_code values.",
                    context={"table": spec.full_name, "count": len(missing_rows), "examples": missing_rows[:10]},
                )
            )

        invalid_rows: list[dict[str, object]] = []
        for row in rows:
            raw_code = row[1]
            if raw_code is None:
                continue
            code = str(raw_code).strip().upper()
            if is_aggregate_only_team_code(code):
                invalid_rows.append({spec.grain_column: row[0], "source_team_code": code, "reason": "tot_not_supported"})
                continue
            if is_multi_team_marker(code) or code in known_real_codes:
                continue
            invalid_rows.append({spec.grain_column: row[0], "source_team_code": code, "reason": "unknown_team_code"})

        if invalid_rows:
            issues.append(
                OfficialStatsValidationIssue(
                    code="invalid_aggregate_source_team_code",
                    message=f"Invalid source_team_code values were found in stats.{spec.table_name}.",
                    context={"table": spec.full_name, "count": len(invalid_rows), "examples": invalid_rows[:10]},
                )
            )
    return issues


def _regular_postseason_separation_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    issues: list[OfficialStatsValidationIssue] = []
    for spec in STATS_TABLE_SPECS:
        table = reflected_tables.get(spec.table_name)
        if table is None:
            continue

        lineage_columns = [name for name in ("source_url", "cache_path", "parser_version") if name in table.c]
        if not lineage_columns:
            continue

        violations: list[dict[str, object]] = []
        for row in session.execute(select(table)).mappings():
            mapping = dict(row)
            lineage_values = [
                str(mapping.get(column) or "").lower()
                for column in lineage_columns
            ]
            has_postseason_marker = any(
                marker in value
                for value in lineage_values
                for marker in _POSTSEASON_MARKERS
            )

            if (
                (spec.season_type == "regular" and has_postseason_marker)
                or (spec.season_type == "postseason" and not has_postseason_marker)
            ):
                violations.append(
                    {
                        spec.grain_column: mapping.get(spec.grain_column),
                        "parser_version": mapping.get("parser_version"),
                        "source_url": mapping.get("source_url"),
                    }
                )

        if violations:
            issues.append(
                OfficialStatsValidationIssue(
                    code="regular_postseason_separation_violation",
                    message=f"Lineage metadata suggests mixed season-type rows in stats.{spec.table_name}.",
                    context={"table": spec.full_name, "count": len(violations), "examples": violations[:10]},
                )
            )
    return issues


def _coverage_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
    core_tables: Mapping[str, Table],
    *,
    coverage_artifact: Mapping[str, object] | None,
    coverage_cache_root: str | Path | None,
) -> tuple[list[OfficialStatsValidationIssue], dict[str, object]]:
    """Diff persisted stats natural keys against the F4E-017 cache-derived oracle.

    Aggregate totals alone cannot see one missing key offset by one unexpected
    key; this compares the actual sets. Every failure mode below stops
    comparison rather than guessing: a missing artifact, an unsupported schema,
    a malformed shape, or a stale fingerprint are all named issues, and the
    rest of `validate_official_stats` still runs and reports regardless.
    """

    if coverage_artifact is None:
        return (
            [
                OfficialStatsValidationIssue(
                    code="coverage_artifact_missing",
                    message="No stats-coverage artifact was supplied; row-level coverage was not verified.",
                    context={"count": 1},
                )
            ],
            {"status": "missing"},
        )

    try:
        artifact = parse_stats_coverage_artifact(coverage_artifact)
    except StatsCoverageSchemaError as exc:
        return (
            [
                OfficialStatsValidationIssue(
                    code="coverage_artifact_schema_unsupported",
                    message=str(exc),
                    context={"count": 1},
                )
            ],
            {"status": "schema_unsupported"},
        )
    except StatsCoverageShapeError as exc:
        return (
            [
                OfficialStatsValidationIssue(
                    code="coverage_artifact_invalid",
                    message=str(exc),
                    context={"count": 1},
                )
            ],
            {"status": "invalid"},
        )

    summary: dict[str, object] = {"status": "loaded", "schema_version": artifact.schema_version}

    freshness_status = "unverified"
    if coverage_cache_root is not None:
        try:
            recomputed = compute_cache_fingerprint(coverage_cache_root)
        except PlayerCacheRootNotFoundError as exc:
            summary["freshness_status"] = "error"
            return (
                [
                    OfficialStatsValidationIssue(
                        code="coverage_cache_root_not_found",
                        message=str(exc),
                        context={"count": 1},
                    )
                ],
                summary,
            )
        if recomputed.digest != artifact.cache_fingerprint.digest:
            summary["freshness_status"] = "stale"
            return (
                [
                    OfficialStatsValidationIssue(
                        code="coverage_artifact_stale",
                        message=(
                            "The stats-coverage artifact's cache fingerprint does not match "
                            "the current cache; key comparison was not run."
                        ),
                        context={
                            "count": 1,
                            "artifact_digest": artifact.cache_fingerprint.digest,
                            "recomputed_digest": recomputed.digest,
                        },
                    )
                ],
                summary,
            )
        freshness_status = "verified"
    summary["freshness_status"] = freshness_status

    issues: list[OfficialStatsValidationIssue] = []
    if artifact.unexplained:
        issues.append(
            OfficialStatsValidationIssue(
                code="coverage_unexplained_source",
                message=(
                    "The stats-coverage artifact has cached source seasons it could not "
                    "classify into an expectation."
                ),
                context={
                    "count": len(artifact.unexplained),
                    "examples": [item.to_dict() for item in artifact.unexplained[:10]],
                },
            )
        )
    if artifact.source_issues:
        issues.append(
            OfficialStatsValidationIssue(
                code="coverage_source_issues_present",
                message=(
                    "The stats-coverage artifact has unreadable or malformed cached sources; "
                    "it may understate expected coverage."
                ),
                context={
                    "count": len(artifact.source_issues),
                    "examples": [item.to_dict() for item in artifact.source_issues[:10]],
                },
            )
        )

    loaded_season_years = get_season_years(session)
    in_scope_entries = 0
    excluded_seasons: set[int] = set()
    for entry in artifact.entries:
        if entry.season_year in loaded_season_years:
            in_scope_entries += 1
        else:
            excluded_seasons.add(entry.season_year)
    scope_summary = {
        "league": NBA_LEAGUE,
        "season_years": sorted(loaded_season_years),
        "artifact_entries": len(artifact.entries),
        "in_scope_entries": in_scope_entries,
        "excluded_entries": len(artifact.entries) - in_scope_entries,
        "excluded_seasons": sorted(excluded_seasons),
        "excluded_reason": "season_not_loaded_for_league",
    }
    if not loaded_season_years:
        issues.append(
            OfficialStatsValidationIssue(
                code="coverage_scope_empty",
                message=(
                    f"No {NBA_LEAGUE} seasons are present in core.seasons; "
                    "coverage comparison has no season scope."
                ),
                context={
                    "count": 1,
                    "league": NBA_LEAGUE,
                    "season_years": [],
                },
            )
        )

    dimension_summaries: dict[str, object] = {}
    for dimension_name, specs, postseason, is_team_stint in (
        ("regular_aggregate", REGULAR_AGGREGATE_TABLE_SPECS, False, False),
        ("postseason_aggregate", POSTSEASON_AGGREGATE_TABLE_SPECS, True, False),
        ("regular_team_stint", REGULAR_TEAM_STINT_TABLE_SPECS, False, True),
        ("postseason_team_stint", POSTSEASON_TEAM_STINT_TABLE_SPECS, True, True),
    ):
        if is_team_stint:
            expected, excluded_expected = _expected_team_stint_keys(
                artifact.entries,
                postseason=postseason,
                season_years=loaded_season_years,
            )
            actual = _actual_team_stint_keys(session, reflected_tables, core_tables, specs)
        else:
            expected, excluded_expected = _expected_aggregate_keys(
                artifact.entries,
                postseason=postseason,
                season_years=loaded_season_years,
            )
            actual = _actual_aggregate_keys(session, reflected_tables, core_tables, specs)

        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        dimension_summaries[dimension_name] = {
            "expected": len(expected),
            "actual": len(actual),
            "missing": len(missing),
            "unexpected": len(unexpected),
            "scope": {
                **scope_summary,
                "excluded_expected_keys": len(excluded_expected),
            },
        }
        if missing:
            issues.append(
                OfficialStatsValidationIssue(
                    code=f"coverage_missing_{dimension_name}_row",
                    message=(
                        f"The stats-coverage artifact expects {dimension_name} rows that are "
                        "missing from the persisted stats tables."
                    ),
                    context={
                        "count": len(missing),
                        "examples": _serialize_coverage_keys(missing[:10], team_stint=is_team_stint),
                    },
                )
            )
        if unexpected:
            issues.append(
                OfficialStatsValidationIssue(
                    code=f"coverage_unexpected_{dimension_name}_row",
                    message=(
                        f"The persisted stats tables have {dimension_name} rows the "
                        "stats-coverage artifact does not expect."
                    ),
                    context={
                        "count": len(unexpected),
                        "examples": _serialize_coverage_keys(unexpected[:10], team_stint=is_team_stint),
                    },
                )
            )

    summary["dimensions"] = dimension_summaries
    summary["unexplained_count"] = len(artifact.unexplained)
    summary["source_issues_count"] = len(artifact.source_issues)
    return issues, summary


def _expected_aggregate_keys(
    entries: tuple[StatsCoverageEntry, ...],
    *,
    postseason: bool,
    season_years: Collection[int],
) -> tuple[set[tuple[str, int, str]], set[tuple[str, int, str]]]:
    keys: set[tuple[str, int, str]] = set()
    excluded_keys: set[tuple[str, int, str]] = set()
    for entry in entries:
        tables = entry.postseason_aggregate_tables if postseason else entry.regular_aggregate_tables
        target = (
            excluded_keys
            if entry.season_year not in season_years
            else keys
        )
        for table in tables:
            target.add((entry.basketball_reference_player_id, entry.season_year, table))
    return keys, excluded_keys


def _expected_team_stint_keys(
    entries: tuple[StatsCoverageEntry, ...],
    *,
    postseason: bool,
    season_years: Collection[int],
) -> tuple[set[tuple[str, int, str, str]], set[tuple[str, int, str, str]]]:
    keys: set[tuple[str, int, str, str]] = set()
    excluded_keys: set[tuple[str, int, str, str]] = set()
    for entry in entries:
        stints = entry.postseason_team_stints if postseason else entry.regular_team_stints
        target = (
            excluded_keys
            if entry.season_year not in season_years
            else keys
        )
        for stint in stints:
            target.add(
                (
                    entry.basketball_reference_player_id,
                    entry.season_year,
                    stint.team_code.strip().upper(),
                    stint.table,
                )
            )
    return keys, excluded_keys


def _actual_aggregate_keys(
    session: Session,
    reflected_tables: Mapping[str, Table],
    core_tables: Mapping[str, Table],
    specs: tuple[StatsTableSpec, ...],
) -> set[tuple[str, int, str]]:
    players = core_tables["players"]
    seasons = core_tables["seasons"]
    player_seasons = core_tables["player_seasons"]

    keys: set[tuple[str, int, str]] = set()
    for spec in specs:
        table = reflected_tables.get(spec.table_name)
        if table is None or spec.grain_column not in table.c:
            # Missing table/column is already reported by
            # `_schema_requirement_issues`; not this comparison's job.
            continue
        grain = table.c[spec.grain_column]
        # The natural key stores season_year but not league, so filter the
        # joined season before reducing rows to that key.
        statement = (
            select(players.c.basketball_reference_player_id, seasons.c.season_year)
            .select_from(table)
            .join(player_seasons, grain == player_seasons.c.id)
            .join(players, player_seasons.c.player_id == players.c.id)
            .join(seasons, player_seasons.c.season_id == seasons.c.id)
            .where(seasons.c.league == NBA_LEAGUE)
        )
        for player_id, season_year in session.execute(statement):
            if player_id is None or season_year is None:
                # Orphan/invalid grain chains are already reported by
                # `_fk_grain_issues`.
                continue
            keys.add((str(player_id), int(season_year), spec.full_name))
    return keys


def _actual_team_stint_keys(
    session: Session,
    reflected_tables: Mapping[str, Table],
    core_tables: Mapping[str, Table],
    specs: tuple[StatsTableSpec, ...],
) -> set[tuple[str, int, str, str]]:
    players = core_tables["players"]
    seasons = core_tables["seasons"]
    player_seasons = core_tables["player_seasons"]
    player_team_seasons = core_tables["player_team_seasons"]
    team_seasons = core_tables["team_seasons"]

    keys: set[tuple[str, int, str, str]] = set()
    for spec in specs:
        table = reflected_tables.get(spec.table_name)
        if table is None or spec.grain_column not in table.c:
            continue
        grain = table.c[spec.grain_column]
        # The natural key stores season_year but not league, so filter the
        # joined season before reducing rows to that key.
        statement = (
            select(
                players.c.basketball_reference_player_id,
                seasons.c.season_year,
                team_seasons.c.team_abbreviation,
            )
            .select_from(table)
            .join(player_team_seasons, grain == player_team_seasons.c.id)
            .join(player_seasons, player_team_seasons.c.player_season_id == player_seasons.c.id)
            .join(players, player_seasons.c.player_id == players.c.id)
            .join(seasons, player_seasons.c.season_id == seasons.c.id)
            .join(team_seasons, player_team_seasons.c.team_season_id == team_seasons.c.id)
            .where(seasons.c.league == NBA_LEAGUE)
        )
        for player_id, season_year, team_abbreviation in session.execute(statement):
            if player_id is None or season_year is None or team_abbreviation is None:
                continue
            keys.add(
                (str(player_id), int(season_year), str(team_abbreviation).strip().upper(), spec.full_name)
            )
    return keys


def _serialize_coverage_keys(
    keys: list[tuple[str, int, str]] | list[tuple[str, int, str, str]],
    *,
    team_stint: bool,
) -> list[dict[str, object]]:
    if team_stint:
        return [
            {
                "basketball_reference_player_id": key[0],
                "season_year": key[1],
                "team_code": key[2],
                "table": key[3],
            }
            for key in keys  # type: ignore[misc]
        ]
    return [
        {"basketball_reference_player_id": key[0], "season_year": key[1], "table": key[2]}
        for key in keys  # type: ignore[misc]
    ]


_PARSER_ISSUE_DESCRIPTIONS = {
    "unknown_parser_version": "an unknown",
    "stale_parser_version": "a stale",
    "wrong_producer_parser_version": "a wrong-producer",
}


def _parser_version_issues(
    session: Session,
    reflected_tables: Mapping[str, Table],
) -> list[OfficialStatsValidationIssue]:
    """Fail on parser lineage the registry doesn't recognize, has superseded,
    or that was written by a different producer than this table expects.

    A `parser_version` value can be individually known and current in the
    registry while still being wrong here: `team-season-parser-v1` is current
    for `team_season`, but a `player_page_regular` table such as
    `stats.player_season_totals` must never carry it — the two producers write
    different tables with different selectors. That mismatch is checked
    independently of staleness so a current-but-wrong-producer version is not
    silently accepted.

    Grouped by `(table, parser_version)` rather than emitted per row, so a
    table with thousands of rows under one bad version produces one issue with
    capped example grains, not thousands of issues.
    """

    issues: list[OfficialStatsValidationIssue] = []
    for spec in STATS_TABLE_SPECS:
        table = reflected_tables.get(spec.table_name)
        if table is None or "parser_version" not in table.c:
            continue

        grain = table.c[spec.grain_column]
        parser_version = table.c["parser_version"]
        groups: dict[str, list[object]] = {}
        for row in session.execute(select(grain, parser_version).select_from(table)):
            groups.setdefault(row[1], []).append(row[0])

        for version, grains in groups.items():
            status = classify_parser_version(version)
            if status == "unknown":
                code = "unknown_parser_version"
            else:
                contract = PARSER_CONTRACTS_BY_IDENTIFIER[version]
                if contract.producer != spec.expected_parser_producer:
                    code = "wrong_producer_parser_version"
                elif status == "stale":
                    code = "stale_parser_version"
                else:
                    continue

            issues.append(
                OfficialStatsValidationIssue(
                    code=code,
                    message=(
                        f"stats.{spec.table_name} has rows with "
                        f"{_PARSER_ISSUE_DESCRIPTIONS[code]} parser_version {version!r}."
                    ),
                    context={
                        "table": spec.full_name,
                        "parser_version": version,
                        "count": len(grains),
                        "examples": grains[:10],
                    },
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
                        "count": null_count,
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
                        "count": numeric_count,
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

        if number < 0 and column_name not in _SIGNED_NUMERIC_COLUMNS:
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
        elif column_name in _SPECIAL_RATE_RANGES:
            minimum, maximum = _SPECIAL_RATE_RANGES[column_name]
            if not _is_between(number, minimum, maximum):
                violations.append(f"{column_name} outside {minimum}-{maximum}")
        elif (
            column_name in _ADVANCED_PERCENTAGE_COLUMNS or column_name in _PBP_POSITION_COLUMNS
        ) and not _is_between(number, 0, 100):
            violations.append(f"{column_name} outside 0-100")
        elif column_name in _TWO_POINT_PERCENTAGE_COLUMNS and not _is_between(number, 0, 2):
            violations.append(f"{column_name} outside 0-2")
        elif (
            column_name.startswith("adj_")
            and column_name.endswith("_pct")
            and column_name not in _SPECIAL_RATE_RANGES
            and not _is_between(number, 0, 300)
        ):
            violations.append(f"{column_name} outside 0-300")
        elif (
            column_name.endswith("_pct")
            and column_name not in _ADVANCED_PERCENTAGE_COLUMNS
            and column_name not in _PBP_POSITION_COLUMNS
            and column_name not in _TWO_POINT_PERCENTAGE_COLUMNS
            and column_name not in _SPECIAL_RATE_RANGES
            and not column_name.startswith("adj_")
            and not _is_between(number, 0, 1)
        ):
            violations.append(f"{column_name} outside 0-1")

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
            context={"count": len(offenders), "objects": offenders[:25]},
        )
    ]


def _backfill_report_issues(
    table_counts: Mapping[str, int],
    backfill_summary: Mapping[str, object],
    stats_backfill_reports: Mapping[str, Any] | None,
) -> list[OfficialStatsValidationIssue]:
    reports = _normalize_backfill_reports(stats_backfill_reports)
    if not reports:
        return []

    issues: list[OfficialStatsValidationIssue] = []
    persisted_total_rows = sum(table_counts.values())
    missing_producers = [kind for kind in STATS_BACKFILL_REPORT_KINDS if kind not in reports]
    if missing_producers:
        issues.append(
            OfficialStatsValidationIssue(
                code="stats_backfill_report_missing_producer",
                message=(
                    "Stats backfill report set is incomplete; missing "
                    + ", ".join(_REPORT_LABELS[kind] for kind in missing_producers)
                    + "."
                ),
                context={
                    "count": len(missing_producers),
                    "missing_producers": missing_producers,
                },
            )
        )

    reported_total_rows = 0
    row_counts_valid = True
    for kind, report in reports.items():
        for field_name in _REPORT_ROW_COUNT_FIELDS[kind]:
            if field_name not in report:
                row_counts_valid = False
                issues.append(
                    OfficialStatsValidationIssue(
                        code="stats_backfill_report_missing_field",
                        message=(
                            f"{_REPORT_LABELS[kind].capitalize()} backfill report is missing "
                            f"{field_name}."
                        ),
                        context={
                            "count": 1,
                            "report_kind": kind,
                            "field": field_name,
                        },
                    )
                )
                continue

            value = report[field_name]
            if not _is_count(value):
                row_counts_valid = False
                issues.append(
                    OfficialStatsValidationIssue(
                        code="stats_backfill_report_invalid_field",
                        message=(
                            f"{_REPORT_LABELS[kind].capitalize()} backfill report field "
                            f"{field_name} must be a non-negative integer."
                        ),
                        context={
                            "count": 1,
                            "report_kind": kind,
                            "field": field_name,
                            "value": value,
                        },
                    )
                )
                continue
            reported_total_rows += int(value)

        issues.extend(_report_metadata_issues(kind, report))
        issues.extend(_report_failure_counter_issues(kind, report))

    if not missing_producers and row_counts_valid and reported_total_rows != persisted_total_rows:
        issues.append(
            OfficialStatsValidationIssue(
                code="backfill_row_mismatch",
                message=(
                    f"Persisted stats rows total {persisted_total_rows}; "
                    f"the three stats backfill reports loaded {reported_total_rows} rows."
                ),
                context={
                    "count": 1,
                    "persisted_total_rows": persisted_total_rows,
                    "reported_total_rows": reported_total_rows,
                },
            )
        )
    return issues


def _extract_backfill_summary(stats_backfill_reports: Mapping[str, Any] | None) -> dict[str, object]:
    reports = _normalize_backfill_reports(stats_backfill_reports)
    if not reports:
        return {}

    missing_producers = [kind for kind in STATS_BACKFILL_REPORT_KINDS if kind not in reports]
    summary: dict[str, object] = {
        "supplied_producers": list(reports),
        "missing_producers": missing_producers,
        "reported_total_rows": 0,
    }
    reported_total_rows = 0
    for kind, report in reports.items():
        fields = list(_REPORT_ROW_COUNT_FIELDS[kind])
        for aliases in _REPORT_FAILURE_FIELDS[kind].values():
            fields.extend(aliases)
        fields.extend(_PLAYER_REPORT_METADATA_FIELDS if kind != "team_stats" else ())
        report_summary = {
            field_name: report[field_name]
            for field_name in dict.fromkeys(fields)
            if field_name in report
        }
        contribution = _report_row_count(kind, report)
        if contribution is not None:
            report_summary["reported_rows"] = contribution
            reported_total_rows += contribution
        summary[kind] = report_summary

    summary["reported_total_rows"] = reported_total_rows
    return summary


def _normalize_backfill_reports(
    stats_backfill_reports: Mapping[str, Any] | None,
) -> dict[StatsBackfillReportKind, Mapping[str, Any]]:
    if not stats_backfill_reports:
        return {}

    reports: dict[StatsBackfillReportKind, Mapping[str, Any]] = {}
    for key, value in stats_backfill_reports.items():
        kind = _REPORT_KIND_ALIASES.get(key)
        if kind is None or not isinstance(value, Mapping):
            continue
        reports[kind] = value
    return {kind: reports[kind] for kind in STATS_BACKFILL_REPORT_KINDS if kind in reports}


def _report_row_count(
    kind: StatsBackfillReportKind,
    report: Mapping[str, Any],
) -> int | None:
    values: list[int] = []
    for field_name in _REPORT_ROW_COUNT_FIELDS[kind]:
        value = report.get(field_name)
        if not _is_count(value):
            return None
        values.append(int(value))
    return sum(values)


def _report_failure_counter_issues(
    kind: StatsBackfillReportKind,
    report: Mapping[str, Any],
) -> list[OfficialStatsValidationIssue]:
    issues: list[OfficialStatsValidationIssue] = []
    nonzero_counters: dict[str, object] = {}

    for counter_name, aliases in _REPORT_FAILURE_FIELDS[kind].items():
        present = [(field_name, report[field_name]) for field_name in aliases if field_name in report]
        if not present:
            issues.append(
                OfficialStatsValidationIssue(
                    code="stats_backfill_report_missing_failure_counter",
                    message=(
                        f"{_REPORT_LABELS[kind].capitalize()} backfill report is missing "
                        f"the {counter_name} failure counter."
                    ),
                    context={
                        "count": 1,
                        "report_kind": kind,
                        "counter": counter_name,
                        "accepted_fields": aliases,
                    },
                )
            )
            continue

        invalid_fields = [field_name for field_name, value in present if not _is_count(value)]
        if invalid_fields:
            issues.append(
                OfficialStatsValidationIssue(
                    code="stats_backfill_report_invalid_failure_counter",
                    message=(
                        f"{_REPORT_LABELS[kind].capitalize()} backfill report failure counters "
                        "must be non-negative integers."
                    ),
                    context={
                        "count": len(invalid_fields),
                        "report_kind": kind,
                        "counter": counter_name,
                        "fields": invalid_fields,
                    },
                )
            )
            continue

        nonzero_values = {
            field_name: value
            for field_name, value in present
            if isinstance(value, int) and not isinstance(value, bool) and value != 0
        }
        if nonzero_values:
            nonzero_counters[counter_name] = nonzero_values

    if nonzero_counters:
        issues.append(
            OfficialStatsValidationIssue(
                code="backfill_failures_present",
                message=(
                    f"{_REPORT_LABELS[kind].capitalize()} backfill report contains nonzero "
                    "failure, quarantine, or unresolved counters."
                ),
                context={
                    "count": len(nonzero_counters),
                    "report_kind": kind,
                    "counters": nonzero_counters,
                },
            )
        )
    return issues


def _report_metadata_issues(
    kind: StatsBackfillReportKind,
    report: Mapping[str, Any],
) -> list[OfficialStatsValidationIssue]:
    if kind == "team_stats":
        return []

    issues: list[OfficialStatsValidationIssue] = []
    cache_root = report.get("cache_root")
    if "cache_root" in report and (
        not isinstance(cache_root, str)
        or not cache_root.strip()
        or not (Path(cache_root).is_absolute() or PureWindowsPath(cache_root).is_absolute())
    ):
        issues.append(
            OfficialStatsValidationIssue(
                code="stats_backfill_report_invalid_metadata",
                message=(
                    f"{_REPORT_LABELS[kind].capitalize()} backfill report cache_root must be "
                    "a resolved absolute path."
                ),
                context={"count": 1, "report_kind": kind, "field": "cache_root"},
            )
        )

    discovery_status = report.get("discovery_status")
    if "discovery_status" in report and discovery_status not in {"ok", "no_matching_pages"}:
        issues.append(
            OfficialStatsValidationIssue(
                code="stats_backfill_report_invalid_metadata",
                message=(
                    f"{_REPORT_LABELS[kind].capitalize()} backfill report discovery_status "
                    "must be ok or no_matching_pages."
                ),
                context={"count": 1, "report_kind": kind, "field": "discovery_status"},
            )
        )
    return issues


def _is_count(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _build_validation_summary(
    issues: list[OfficialStatsValidationIssue],
) -> dict[str, int]:
    summary = {
        "missing_table_issues": 0,
        "missing_column_issues": 0,
        "constraint_issues": 0,
        "duplicate_grain_rows": 0,
        "orphan_rows": 0,
        "invalid_core_grain_rows": 0,
        "synthetic_code_violations": 0,
        "source_metadata_violations": 0,
        "regular_postseason_separation_violations": 0,
        "parser_lineage_violations": 0,
        "numeric_range_violations": 0,
        "all_null_data_rows": 0,
        "generated_metric_schema_objects": 0,
        "backfill_report_violations": 0,
        "coverage_violations": 0,
    }
    issue_groups = {
        "missing_stats_table": "missing_table_issues",
        "missing_required_column": "missing_column_issues",
        "unexpected_source_team_code_column": "missing_column_issues",
        "invalid_fk_constraint": "constraint_issues",
        "missing_unique_grain_constraint": "constraint_issues",
        "duplicate_logical_rows": "duplicate_grain_rows",
        "orphan_fk_grain": "orphan_rows",
        "invalid_core_grain_chain": "invalid_core_grain_rows",
        "synthetic_code_in_core_teams": "synthetic_code_violations",
        "synthetic_code_in_core_team_aliases": "synthetic_code_violations",
        "synthetic_code_in_core_team_seasons": "synthetic_code_violations",
        "synthetic_code_in_core_player_team_seasons": "synthetic_code_violations",
        "synthetic_code_in_team_stint_stats": "synthetic_code_violations",
        "missing_source_team_code_value": "source_metadata_violations",
        "invalid_aggregate_source_team_code": "source_metadata_violations",
        "regular_postseason_separation_violation": "regular_postseason_separation_violations",
        "unknown_parser_version": "parser_lineage_violations",
        "stale_parser_version": "parser_lineage_violations",
        "wrong_producer_parser_version": "parser_lineage_violations",
        "impossible_numeric_values": "numeric_range_violations",
        "all_stat_columns_null": "all_null_data_rows",
        "generated_metric_schema_name": "generated_metric_schema_objects",
        "stats_backfill_report_missing_field": "backfill_report_violations",
        "stats_backfill_report_invalid_field": "backfill_report_violations",
        "stats_backfill_report_missing_producer": "backfill_report_violations",
        "stats_backfill_report_missing_failure_counter": "backfill_report_violations",
        "stats_backfill_report_invalid_failure_counter": "backfill_report_violations",
        "stats_backfill_report_invalid_metadata": "backfill_report_violations",
        "backfill_row_mismatch": "backfill_report_violations",
        "backfill_failures_present": "backfill_report_violations",
        "coverage_artifact_missing": "coverage_violations",
        "coverage_artifact_schema_unsupported": "coverage_violations",
        "coverage_artifact_invalid": "coverage_violations",
        "coverage_cache_root_not_found": "coverage_violations",
        "coverage_artifact_stale": "coverage_violations",
        "coverage_unexplained_source": "coverage_violations",
        "coverage_source_issues_present": "coverage_violations",
        "coverage_scope_empty": "coverage_violations",
        "coverage_missing_regular_aggregate_row": "coverage_violations",
        "coverage_unexpected_regular_aggregate_row": "coverage_violations",
        "coverage_missing_postseason_aggregate_row": "coverage_violations",
        "coverage_unexpected_postseason_aggregate_row": "coverage_violations",
        "coverage_missing_regular_team_stint_row": "coverage_violations",
        "coverage_unexpected_regular_team_stint_row": "coverage_violations",
        "coverage_missing_postseason_team_stint_row": "coverage_violations",
        "coverage_unexpected_postseason_team_stint_row": "coverage_violations",
    }

    for issue in issues:
        target = issue_groups.get(issue.code)
        if target is None:
            continue
        count = issue.context.get("count", 1)
        summary[target] += int(count) if isinstance(count, int | float) else 1
    return summary


def _matched_tokens(name: str) -> tuple[str, ...]:
    lowered = name.lower()
    return tuple(token for token in _BANNED_GENERATED_NAME_TOKENS if token in lowered)


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
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, tuple | list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def _json_safe_mapping(mapping: Mapping[str, object]) -> dict[str, object]:
    return {key: _json_safe_value(value) for key, value in mapping.items()}


__all__ = [
    "OfficialStatsValidationIssue",
    "OfficialStatsValidationReport",
    "POSTSEASON_AGGREGATE_TABLE_SPECS",
    "POSTSEASON_TEAM_STINT_TABLE_SPECS",
    "REGULAR_AGGREGATE_TABLE_SPECS",
    "REGULAR_TEAM_STINT_TABLE_SPECS",
    "STATS_TABLE_SPECS",
    "StatsTableSpec",
    "validate_official_stats",
]
