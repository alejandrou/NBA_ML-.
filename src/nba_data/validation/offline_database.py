from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from nba_data.db.base import Base
from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.domain.team_codes import is_synthetic_team_code

DEFAULT_PHASE_4D_TABLE_COUNTS = {
    "core.seasons": 26,
    "core.teams": 37,
    "core.team_aliases": 775,
    "core.team_seasons": 775,
    "core.players": 2551,
    "core.player_seasons": 12676,
    "core.player_team_seasons": 14344,
}


@dataclass(frozen=True)
class OfflineDatabaseValidationExpectations:
    table_counts: Mapping[str, int] = field(
        default_factory=lambda: dict(DEFAULT_PHASE_4D_TABLE_COUNTS)
    )
    league: str = "NBA"
    expected_start_year: int = 2000
    expected_end_year: int = 2025
    min_team_seasons_per_season: int = 29
    min_player_seasons_per_season: int = 400
    min_player_team_seasons_per_season: int = 400
    max_team_seasons_without_players: int = 0
    expected_backfill_selected_inventory_entries: int = 775
    expected_backfill_loaded_entries: int = 775
    expected_backfill_loaded_rows: int = 129000
    expected_backfill_failed_entries: int = 0
    expected_backfill_quarantined_entries: int = 0
    expected_backfill_quarantined_rows: int = 0

    @property
    def expected_season_years(self) -> tuple[int, ...]:
        return tuple(range(self.expected_start_year, self.expected_end_year + 1))


@dataclass(frozen=True)
class OfflineDatabaseValidationIssue:
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
class OfflineDatabaseValidationReport:
    passed: bool
    table_counts: Mapping[str, int]
    season_counts: tuple[dict[str, int], ...]
    backfill_summary: Mapping[str, object]
    issues: tuple[OfflineDatabaseValidationIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "table_counts": dict(self.table_counts),
            "season_counts": list(self.season_counts),
            "backfill_summary": dict(self.backfill_summary),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_offline_database(
    session: Session,
    backfill_report: Mapping[str, Any] | None,
    expectations: OfflineDatabaseValidationExpectations | None = None,
) -> OfflineDatabaseValidationReport:
    """Validate the Phase 4D offline core database state without mutating it."""

    resolved_expectations = expectations or OfflineDatabaseValidationExpectations()
    table_counts = _load_table_counts(session)
    season_counts = _load_season_counts(session, resolved_expectations.league)
    backfill_summary = _extract_backfill_summary(backfill_report)

    issues: list[OfflineDatabaseValidationIssue] = []
    issues.extend(_table_count_issues(table_counts, resolved_expectations))
    issues.extend(_season_coverage_issues(season_counts, resolved_expectations))
    issues.extend(_duplicate_issues(session))
    issues.extend(_orphan_issues(session))
    issues.extend(_team_season_player_issues(session, resolved_expectations))
    issues.extend(_synthetic_team_code_issues(session))
    issues.extend(_player_identifier_issues(session))
    issues.extend(_backfill_report_issues(backfill_report, backfill_summary, resolved_expectations))

    return OfflineDatabaseValidationReport(
        passed=not issues,
        table_counts=table_counts,
        season_counts=season_counts,
        backfill_summary=backfill_summary,
        issues=tuple(issues),
    )


def _load_table_counts(session: Session) -> dict[str, int]:
    return {
        "core.seasons": _count(session, Season),
        "core.teams": _count(session, Team),
        "core.team_aliases": _count(session, TeamAlias),
        "core.team_seasons": _count(session, TeamSeason),
        "core.players": _count(session, Player),
        "core.player_seasons": _count(session, PlayerSeason),
        "core.player_team_seasons": _count(session, PlayerTeamSeason),
    }


def _load_season_counts(session: Session, league: str) -> tuple[dict[str, int], ...]:
    statement = (
        select(
            Season.season_year,
            func.count(TeamSeason.id.distinct()).label("team_seasons"),
            func.count(PlayerSeason.id.distinct()).label("player_seasons"),
            func.count(PlayerTeamSeason.id.distinct()).label("player_team_seasons"),
        )
        .select_from(Season)
        .outerjoin(TeamSeason, TeamSeason.season_id == Season.id)
        .outerjoin(PlayerSeason, PlayerSeason.season_id == Season.id)
        .outerjoin(PlayerTeamSeason, PlayerTeamSeason.team_season_id == TeamSeason.id)
        .where(Season.league == league)
        .group_by(Season.season_year)
        .order_by(Season.season_year)
    )
    return tuple(
        {
            "season_year": int(row.season_year),
            "team_seasons": int(row.team_seasons),
            "player_seasons": int(row.player_seasons),
            "player_team_seasons": int(row.player_team_seasons),
        }
        for row in session.execute(statement)
    )


def _table_count_issues(
    table_counts: Mapping[str, int],
    expectations: OfflineDatabaseValidationExpectations,
) -> list[OfflineDatabaseValidationIssue]:
    issues: list[OfflineDatabaseValidationIssue] = []
    for table_name, expected_count in expectations.table_counts.items():
        actual_count = table_counts.get(table_name, 0)
        if actual_count != expected_count:
            issues.append(
                OfflineDatabaseValidationIssue(
                    code="table_count_mismatch",
                    message=(
                        f"{table_name} has {actual_count} rows; expected {expected_count}."
                    ),
                    context={
                        "table": table_name,
                        "actual": actual_count,
                        "expected": expected_count,
                    },
                )
            )
    return issues


def _season_coverage_issues(
    season_counts: tuple[dict[str, int], ...],
    expectations: OfflineDatabaseValidationExpectations,
) -> list[OfflineDatabaseValidationIssue]:
    issues: list[OfflineDatabaseValidationIssue] = []
    actual_years = tuple(row["season_year"] for row in season_counts)
    expected_years = expectations.expected_season_years
    missing_years = tuple(year for year in expected_years if year not in actual_years)
    extra_years = tuple(year for year in actual_years if year not in expected_years)
    if missing_years or extra_years:
        issues.append(
            OfflineDatabaseValidationIssue(
                code="season_coverage_mismatch",
                message="Loaded seasons do not match the expected Phase 4D season range.",
                context={"missing_years": missing_years, "extra_years": extra_years},
            )
        )

    for row in season_counts:
        if row["team_seasons"] < expectations.min_team_seasons_per_season:
            issues.append(
                OfflineDatabaseValidationIssue(
                    code="season_team_count_low",
                    message=(
                        f"Season {row['season_year']} has {row['team_seasons']} "
                        "team seasons."
                    ),
                    context=dict(row),
                )
            )
        if row["player_seasons"] < expectations.min_player_seasons_per_season:
            issues.append(
                OfflineDatabaseValidationIssue(
                    code="season_player_count_low",
                    message=(
                        f"Season {row['season_year']} has {row['player_seasons']} "
                        "player seasons."
                    ),
                    context=dict(row),
                )
            )
        if row["player_team_seasons"] < expectations.min_player_team_seasons_per_season:
            issues.append(
                OfflineDatabaseValidationIssue(
                    code="season_player_team_count_low",
                    message=(
                        f"Season {row['season_year']} has "
                        f"{row['player_team_seasons']} player-team seasons."
                    ),
                    context=dict(row),
                )
            )
    return issues


def _duplicate_issues(session: Session) -> list[OfflineDatabaseValidationIssue]:
    checks = (
        ("duplicate_seasons", Season, (Season.league, Season.season_year)),
        ("duplicate_teams", Team, (Team.basketball_reference_team_id,)),
        (
            "duplicate_team_aliases",
            TeamAlias,
            (
                TeamAlias.team_id,
                TeamAlias.abbreviation,
                TeamAlias.from_season_year,
                TeamAlias.to_season_year,
            ),
        ),
        ("duplicate_team_seasons_by_team", TeamSeason, (TeamSeason.team_id, TeamSeason.season_id)),
        (
            "duplicate_team_seasons_by_abbreviation",
            TeamSeason,
            (TeamSeason.season_id, TeamSeason.team_abbreviation),
        ),
        (
            "duplicate_player_seasons",
            PlayerSeason,
            (PlayerSeason.player_id, PlayerSeason.season_id),
        ),
        (
            "duplicate_player_team_seasons",
            PlayerTeamSeason,
            (PlayerTeamSeason.player_season_id, PlayerTeamSeason.team_season_id),
        ),
    )
    issues: list[OfflineDatabaseValidationIssue] = []
    for code, model, columns in checks:
        rows = _duplicate_rows(session, model, columns)
        if rows:
            issues.append(
                OfflineDatabaseValidationIssue(
                    code=code,
                    message=f"Duplicate logical rows found for {model.__tablename__}.",
                    context={"duplicate_groups": len(rows), "examples": rows[:10]},
                )
            )
    return issues


def _duplicate_rows(session: Session, model: type, columns: tuple[Any, ...]) -> list[dict[str, object]]:
    statement = (
        select(*columns, func.count().label("row_count"))
        .select_from(model)
        .group_by(*columns)
        .having(func.count() > 1)
    )
    rows = []
    for row in session.execute(statement):
        item = {column.key: value for column, value in zip(columns, row[:-1], strict=True)}
        item["row_count"] = row.row_count
        rows.append(item)
    return rows


def _orphan_issues(session: Session) -> list[OfflineDatabaseValidationIssue]:
    checks = {
        "orphan_team_aliases_team": _missing_parent_count(
            session,
            TeamAlias,
            Team,
            TeamAlias.team_id == Team.id,
            parent_id=Team.id,
        ),
        "orphan_team_seasons_team": _missing_parent_count(
            session,
            TeamSeason,
            Team,
            TeamSeason.team_id == Team.id,
            parent_id=Team.id,
        ),
        "orphan_team_seasons_season": _missing_parent_count(
            session,
            TeamSeason,
            Season,
            TeamSeason.season_id == Season.id,
            parent_id=Season.id,
        ),
        "orphan_player_seasons_player": _missing_parent_count(
            session,
            PlayerSeason,
            Player,
            PlayerSeason.player_id == Player.id,
            parent_id=Player.id,
        ),
        "orphan_player_seasons_season": _missing_parent_count(
            session,
            PlayerSeason,
            Season,
            PlayerSeason.season_id == Season.id,
            parent_id=Season.id,
        ),
        "orphan_player_team_seasons_player_season": _missing_parent_count(
            session,
            PlayerTeamSeason,
            PlayerSeason,
            PlayerTeamSeason.player_season_id == PlayerSeason.id,
            parent_id=PlayerSeason.id,
        ),
        "orphan_player_team_seasons_team_season": _missing_parent_count(
            session,
            PlayerTeamSeason,
            TeamSeason,
            PlayerTeamSeason.team_season_id == TeamSeason.id,
            parent_id=TeamSeason.id,
        ),
    }
    return [
        OfflineDatabaseValidationIssue(
            code=code,
            message=f"{count} orphan relationship rows found.",
            context={"count": count},
        )
        for code, count in checks.items()
        if count
    ]


def _team_season_player_issues(
    session: Session,
    expectations: OfflineDatabaseValidationExpectations,
) -> list[OfflineDatabaseValidationIssue]:
    statement = (
        select(
            TeamSeason.id,
            TeamSeason.team_abbreviation,
            Season.season_year,
            func.count(PlayerTeamSeason.id).label("player_team_seasons"),
        )
        .select_from(TeamSeason)
        .join(Season, TeamSeason.season_id == Season.id)
        .outerjoin(PlayerTeamSeason, PlayerTeamSeason.team_season_id == TeamSeason.id)
        .group_by(TeamSeason.id, TeamSeason.team_abbreviation, Season.season_year)
        .having(func.count(PlayerTeamSeason.id) == 0)
        .order_by(Season.season_year, TeamSeason.team_abbreviation)
    )
    rows = [
        {
            "team_season_id": row.id,
            "team_abbreviation": row.team_abbreviation,
            "season_year": row.season_year,
            "player_team_seasons": row.player_team_seasons,
        }
        for row in session.execute(statement)
    ]
    if len(rows) <= expectations.max_team_seasons_without_players:
        return []
    return [
        OfflineDatabaseValidationIssue(
            code="team_seasons_without_players",
            message=f"{len(rows)} team seasons have no player-team-season rows.",
            context={"count": len(rows), "examples": rows[:10]},
        )
    ]


def _synthetic_team_code_issues(session: Session) -> list[OfflineDatabaseValidationIssue]:
    # `TOT` and the team-count markers are an open-ended set, so they are
    # classified in Python rather than enumerated in a SQL predicate. The three
    # `core` identity tables are small enough to scan.
    checks = {
        "teams_synthetic_code_rows": sum(
            1
            for row in session.execute(
                select(Team.basketball_reference_team_id, Team.current_abbreviation)
            )
            if is_synthetic_team_code(row[0]) or is_synthetic_team_code(row[1])
        ),
        "team_aliases_synthetic_code_rows": sum(
            1
            for value in session.scalars(select(TeamAlias.abbreviation))
            if is_synthetic_team_code(value)
        ),
        "team_seasons_synthetic_code_rows": sum(
            1
            for value in session.scalars(select(TeamSeason.team_abbreviation))
            if is_synthetic_team_code(value)
        ),
    }
    return [
        OfflineDatabaseValidationIssue(
            code=code,
            message=f"{count} real-team rows incorrectly use a synthetic team code.",
            context={"count": count},
        )
        for code, count in checks.items()
        if count
    ]


def _player_identifier_issues(session: Session) -> list[OfflineDatabaseValidationIssue]:
    missing = (
        session.scalar(
            select(func.count())
            .select_from(Player)
            .where(
                (Player.basketball_reference_player_id.is_(None))
                | (Player.basketball_reference_player_id == "")
            )
        )
        or 0
    )
    if not missing:
        return []
    return [
        OfflineDatabaseValidationIssue(
            code="players_missing_basketball_reference_id",
            message=(
                f"{missing} players are missing basketball_reference_player_id; "
                "player_name must not be used as a stable key."
            ),
            context={"count": missing},
        )
    ]


def _backfill_report_issues(
    backfill_report: Mapping[str, Any] | None,
    summary: Mapping[str, object],
    expectations: OfflineDatabaseValidationExpectations,
) -> list[OfflineDatabaseValidationIssue]:
    if backfill_report is None:
        return [
            OfflineDatabaseValidationIssue(
                code="backfill_report_missing",
                message="A Phase 4D offline backfill report is required for readiness validation.",
            )
        ]

    checks = {
        "selected_inventory_entries": expectations.expected_backfill_selected_inventory_entries,
        "loaded_entries": expectations.expected_backfill_loaded_entries,
        "loaded_rows": expectations.expected_backfill_loaded_rows,
        "failed_entries": expectations.expected_backfill_failed_entries,
        "quarantined_entries": expectations.expected_backfill_quarantined_entries,
        "quarantined_rows": expectations.expected_backfill_quarantined_rows,
    }
    issues: list[OfflineDatabaseValidationIssue] = []
    for key, expected in checks.items():
        actual = summary.get(key)
        if actual != expected:
            issues.append(
                OfflineDatabaseValidationIssue(
                    code="backfill_report_mismatch",
                    message=f"Backfill report {key} is {actual}; expected {expected}.",
                    context={"field": key, "actual": actual, "expected": expected},
                )
            )
    return issues


def _extract_backfill_summary(backfill_report: Mapping[str, Any] | None) -> dict[str, object]:
    if backfill_report is None:
        return {}

    processing_report = _mapping(backfill_report.get("processing_report"))
    load_report = _mapping(backfill_report.get("load_report"))
    audit_report = _mapping(backfill_report.get("audit_report"))
    return {
        "selected_inventory_entries": backfill_report.get("selected_inventory_entries"),
        "skipped_inventory_entries": backfill_report.get("skipped_inventory_entries"),
        "processing_failed_entries": processing_report.get("failed_entries"),
        "validated_entries": processing_report.get("validated_entries"),
        "validated_row_count": processing_report.get("validated_row_count"),
        "loaded_entries": load_report.get("loaded_entries"),
        "loaded_rows": load_report.get("loaded_rows"),
        "failed_entries": load_report.get("failed_entries"),
        "skipped_entries": load_report.get("skipped_entries"),
        "quarantined_entries": audit_report.get("quarantined_entries"),
        "quarantined_rows": audit_report.get("quarantined_rows"),
    }


def _missing_parent_count(
    session: Session,
    child: type[Base],
    parent: type[Base],
    join_condition: Any,
    *,
    parent_id: InstrumentedAttribute[int],
) -> int:
    """Count `child` rows whose `parent` row is absent.

    `parent_id` names the column the outer join leaves NULL. `Base` declares no
    columns of its own, so the parent class alone cannot supply it.
    """

    return (
        session.scalar(
            select(func.count()).select_from(child).outerjoin(parent, join_condition).where(parent_id.is_(None))
        )
        or 0
    )


def _count(session: Session, model: type[Base]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
