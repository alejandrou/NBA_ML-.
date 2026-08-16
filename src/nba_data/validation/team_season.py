from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nba_data.domain.team_codes import is_aggregate_only_team_code, is_multi_team_marker


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    message: str
    row_index: int | None = None
    source_table: str | None = None


class TeamSeasonDataQualityError(ValueError):
    def __init__(self, issues: list[DataQualityIssue]) -> None:
        self.issues = issues
        summary = "; ".join(issue.message for issue in issues)
        super().__init__(summary)


def validate_normalized_team_season_rows(
    rows: list[dict[str, Any]],
    *,
    required_tables: set[str] | None = None,
    require_stable_player_id: bool = True,
) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    seen_keys: dict[tuple[Any, ...], int] = {}
    table_counts: dict[str, int] = {}

    for index, row in enumerate(rows):
        source_table = _string(row.get("source_table"))
        if source_table:
            table_counts[source_table] = table_counts.get(source_table, 0) + 1

        issues.extend(_context_issues(row, index, source_table))
        issues.extend(_synthetic_team_code_issues(row, index, source_table))

        if require_stable_player_id and _is_player_row(row):
            player_id = _string(row.get("basketball_reference_player_id"))
            if not player_id:
                issues.append(
                    DataQualityIssue(
                        code="missing_player_id",
                        message=(
                            "Player row is missing basketball_reference_player_id; "
                            "do not use player_name as a stable key."
                        ),
                        row_index=index,
                        source_table=source_table,
                    )
                )

        natural_key = _natural_key(row)
        if natural_key is None:
            continue

        duplicate_index = seen_keys.get(natural_key)
        if duplicate_index is not None:
            issues.append(
                DataQualityIssue(
                    code="duplicate_natural_key",
                    message=(
                        "Duplicate normalized team-season row for natural key "
                        f"{natural_key}; first seen at row {duplicate_index}."
                    ),
                    row_index=index,
                    source_table=source_table,
                )
            )
        else:
            seen_keys[natural_key] = index

    for table in sorted(required_tables or set()):
        if table_counts.get(table, 0) == 0:
            issues.append(
                DataQualityIssue(
                    code="required_table_empty",
                    message=f"Required source table '{table}' has no normalized rows.",
                    source_table=table,
                )
            )

    return issues


def assert_valid_normalized_team_season_rows(
    rows: list[dict[str, Any]],
    *,
    required_tables: set[str] | None = None,
    require_stable_player_id: bool = True,
) -> None:
    issues = validate_normalized_team_season_rows(
        rows,
        required_tables=required_tables,
        require_stable_player_id=require_stable_player_id,
    )
    if issues:
        raise TeamSeasonDataQualityError(issues)


def _context_issues(
    row: dict[str, Any], row_index: int, source_table: str | None
) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    for field in ("league", "season_year", "team_abbreviation", "source_table", "stat_scope"):
        if row.get(field) in (None, ""):
            issues.append(
                DataQualityIssue(
                    code="missing_context",
                    message=f"Normalized row is missing required context field '{field}'.",
                    row_index=row_index,
                    source_table=source_table,
                )
            )
    return issues


def _synthetic_team_code_issues(
    row: dict[str, Any], row_index: int, source_table: str | None
) -> list[DataQualityIssue]:
    team_abbreviation = _string(row.get("team_abbreviation"))

    # A team-count marker belongs to player pages, never to a team-season row,
    # so it is wrong in every classification rather than only outside aggregates.
    if is_multi_team_marker(team_abbreviation):
        return [
            DataQualityIssue(
                code="multi_team_marker_not_a_team",
                message=(
                    f"'{team_abbreviation}' is a multi-team marker, not a team; "
                    "it must never appear as team_abbreviation."
                ),
                row_index=row_index,
                source_table=source_table,
            )
        ]

    if not is_aggregate_only_team_code(team_abbreviation):
        return []

    if row.get("team_context") == "aggregate" and row.get("stat_scope") == "player_season_aggregate":
        return []

    return [
        DataQualityIssue(
            code="tot_not_aggregate",
            message="TOT rows must be classified as player-season aggregates, not real teams.",
            row_index=row_index,
            source_table=source_table,
        )
    ]


def _natural_key(row: dict[str, Any]) -> tuple[Any, ...] | None:
    player_id = _string(row.get("basketball_reference_player_id"))
    if not player_id:
        return None

    key_fields = (
        "league",
        "season_year",
        "team_abbreviation",
        "source_table",
        "stat_scope",
        "basketball_reference_player_id",
    )
    values = tuple(row.get(field) for field in key_fields)
    if any(value in (None, "") for value in values):
        return None
    return values


def _is_player_row(row: dict[str, Any]) -> bool:
    return _string(row.get("player_name")) is not None or row.get("stat_scope") in {
        "player_team_season",
        "player_season_aggregate",
        "team_roster",
    }


def _string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None
