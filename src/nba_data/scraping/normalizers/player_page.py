from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nba_data.scraping.normalizers.team_season import _clean_string, _safe_number, _snake_case

MULTI_TEAM_CODES = frozenset({"2TM", "3TM", "4TM"})
IGNORED_TEAM_CODES = frozenset({"TOT"})
_SEASON_RANGE_RE = re.compile(r"^(?P<start>\d{4})-(?P<end>\d{2,4})$")


@dataclass(frozen=True)
class PlayerPageSelectionEntry:
    source_table: str
    season_year: int | None
    source_team_code: str | None
    status: str
    reason: str
    row_count: int = 0


@dataclass(frozen=True)
class PlayerPageNormalizationResult:
    selected_rows: tuple[dict[str, Any], ...]
    selection_entries: tuple[PlayerPageSelectionEntry, ...]
    tables_parsed: int
    rows_selected: int
    rows_skipped: int


def normalize_player_page_regular_season(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    basketball_reference_player_id: str,
    league: str = "NBA",
    start_year: int | None = None,
    end_year: int | None = None,
) -> PlayerPageNormalizationResult:
    """Normalize selected full-season player-page rows without loading or generating stats."""

    player_id = _required_player_id(basketball_reference_player_id)
    selected_rows: list[dict[str, Any]] = []
    selection_entries: list[PlayerPageSelectionEntry] = []
    tables_parsed = 0
    rows_skipped = 0

    for source_table, parsed_rows in parsed.items():
        if parsed_rows:
            tables_parsed += 1

        grouped_rows: dict[int, list[dict[str, str]]] = defaultdict(list)
        invalid_rows = 0
        for parsed_row in parsed_rows:
            season_year = _season_end_year(parsed_row)
            team_code = _team_code(parsed_row)
            if season_year is None or team_code in IGNORED_TEAM_CODES:
                invalid_rows += 1
                continue
            grouped_rows[season_year].append(parsed_row)

        rows_skipped += invalid_rows
        if invalid_rows:
            selection_entries.append(
                PlayerPageSelectionEntry(
                    source_table=source_table,
                    season_year=None,
                    source_team_code=None,
                    status="skipped",
                    reason="ignored_invalid_or_unsupported_rows",
                    row_count=invalid_rows,
                )
            )

        for season_year in sorted(grouped_rows):
            if start_year is not None and season_year < start_year:
                skipped_count = len(grouped_rows[season_year])
                rows_skipped += skipped_count
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=season_year,
                        source_team_code=None,
                        status="skipped",
                        reason="before_start_year",
                        row_count=skipped_count,
                    )
                )
                continue
            if end_year is not None and season_year > end_year:
                skipped_count = len(grouped_rows[season_year])
                rows_skipped += skipped_count
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=season_year,
                        source_team_code=None,
                        status="skipped",
                        reason="after_end_year",
                        row_count=skipped_count,
                    )
                )
                continue

            season_rows = grouped_rows[season_year]
            selected_row, reason = _select_full_season_row(season_rows)
            if selected_row is None:
                rows_skipped += len(season_rows)
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=season_year,
                        source_team_code=None,
                        status="skipped",
                        reason=reason,
                        row_count=len(season_rows),
                    )
                )
                continue

            source_team_code = _team_code(selected_row)
            rows_skipped += max(len(season_rows) - 1, 0)
            selection_entries.append(
                PlayerPageSelectionEntry(
                    source_table=source_table,
                    season_year=season_year,
                    source_team_code=source_team_code,
                    status="selected",
                    reason=reason,
                    row_count=len(season_rows),
                )
            )
            selected_rows.append(
                {
                    "league": league,
                    "season_year": season_year,
                    "source_table": source_table,
                    "stat_scope": "player_season_aggregate",
                    "player_name": _player_name(selected_row),
                    "basketball_reference_player_id": player_id,
                    "stable_player_key": player_id,
                    "identifier_status": "present",
                    "source_team_code": source_team_code,
                    "values": _normalized_values(selected_row),
                }
            )

    return PlayerPageNormalizationResult(
        selected_rows=tuple(selected_rows),
        selection_entries=tuple(selection_entries),
        tables_parsed=tables_parsed,
        rows_selected=len(selected_rows),
        rows_skipped=rows_skipped,
    )


def _required_player_id(value: str) -> str:
    cleaned = _clean_string(value)
    if cleaned is None:
        msg = "basketball_reference_player_id is required."
        raise ValueError(msg)
    return cleaned


def _select_full_season_row(
    season_rows: list[dict[str, str]],
) -> tuple[dict[str, str] | None, str]:
    synthetic_rows = [row for row in season_rows if _team_code(row) in MULTI_TEAM_CODES]
    if synthetic_rows:
        return synthetic_rows[0], "selected_multi_team_aggregate"

    real_team_rows = [row for row in season_rows if _team_code(row) not in MULTI_TEAM_CODES | IGNORED_TEAM_CODES]
    if len(real_team_rows) == 1:
        return real_team_rows[0], "selected_single_team_row"
    if not real_team_rows:
        return None, "no_supported_team_row"
    return None, "ambiguous_multiple_real_team_rows"


def _season_end_year(row: Mapping[str, str]) -> int | None:
    season_value = _clean_string(row.get("season"))
    if season_value is None:
        return None

    if season_value.isdigit() and len(season_value) == 4:
        return int(season_value)

    match = _SEASON_RANGE_RE.fullmatch(season_value)
    if match is None:
        return None

    start_year = int(match.group("start"))
    end_suffix = match.group("end")
    if len(end_suffix) == 4:
        return int(end_suffix)
    century = (start_year // 100) * 100
    return century + int(end_suffix)


def _team_code(row: Mapping[str, str]) -> str | None:
    for key in ("team_id", "team_abbreviation", "team", "tm"):
        value = _clean_string(row.get(key))
        if value:
            return value.upper()
    return None


def _player_name(row: Mapping[str, str]) -> str | None:
    for key in ("name_display", "player", "Player"):
        value = _clean_string(row.get(key))
        if value:
            return value
    return None


def _normalized_values(row: Mapping[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in row.items():
        normalized_key = _snake_case(key)
        if normalized_key in {
            "basketball_reference_player_id",
            "season",
            "team_id",
            "team",
            "tm",
            "team_abbreviation",
            "lg",
            "lg_id",
        }:
            continue
        values[normalized_key] = _safe_number(value)
    return values


__all__ = [
    "IGNORED_TEAM_CODES",
    "MULTI_TEAM_CODES",
    "PlayerPageNormalizationResult",
    "PlayerPageSelectionEntry",
    "normalize_player_page_regular_season",
]
