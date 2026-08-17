from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nba_data.domain.team_codes import is_aggregate_only_team_code, is_multi_team_marker
from nba_data.scraping.normalizers.team_season import _clean_string, _safe_number, _snake_case

# Only the two forms Basketball Reference actually uses: `1999-00` and `1999-2000`.
# A three-digit suffix is malformed, not a short year, and must not be guessed at.
_SEASON_RANGE_RE = re.compile(r"^(?P<start>\d{4})-(?P<end>\d{2}|\d{4})$")
_DID_NOT_PLAY_MARKER = "Did not play -"


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
    unsupported_rows: int = 0


def normalize_player_page_regular_season(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    basketball_reference_player_id: str,
    league: str = "NBA",
    start_year: int | None = None,
    end_year: int | None = None,
) -> PlayerPageNormalizationResult:
    """Normalize selected full-season regular-season player-page rows."""

    return _normalize_player_page_aggregate_only(
        parsed,
        basketball_reference_player_id=basketball_reference_player_id,
        league=league,
        start_year=start_year,
        end_year=end_year,
        stat_scope="player_season_aggregate",
    )


def normalize_player_page_postseason(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    basketball_reference_player_id: str,
    league: str = "NBA",
    start_year: int | None = None,
    end_year: int | None = None,
) -> PlayerPageNormalizationResult:
    """Normalize supported postseason aggregate and team-stint player-page rows."""

    player_id = _required_player_id(basketball_reference_player_id)
    selected_rows: list[dict[str, Any]] = []
    selection_entries: list[PlayerPageSelectionEntry] = []
    tables_parsed = 0
    rows_skipped = 0
    unsupported_rows = 0

    for source_table, parsed_rows in parsed.items():
        if parsed_rows:
            tables_parsed += 1

        grouped_rows: dict[int, list[dict[str, str]]] = defaultdict(list)
        for parsed_row in parsed_rows:
            season_year = _season_end_year(parsed_row)
            team_code = _team_code(parsed_row)
            if season_year is None:
                rows_skipped += 1
                unsupported_rows += 1
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=None,
                        source_team_code=None,
                        status="skipped",
                        reason="invalid_season_row",
                        row_count=1,
                    )
                )
                continue
            if team_code is None:
                rows_skipped += 1
                unsupported_rows += 1
                reason = (
                    "did_not_play_season"
                    if _is_did_not_play_placeholder(parsed_row)
                    else "missing_team_code"
                )
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=season_year,
                        source_team_code=None,
                        status="skipped",
                        reason=reason,
                        row_count=1,
                    )
                )
                continue
            grouped_rows[season_year].append(parsed_row)

        for season_year in sorted(grouped_rows):
            season_rows = grouped_rows[season_year]
            if start_year is not None and season_year < start_year:
                skipped_count = len(season_rows)
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
                skipped_count = len(season_rows)
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

            synthetic_rows = [row for row in season_rows if is_multi_team_marker(_team_code(row))]
            tot_rows = [row for row in season_rows if is_aggregate_only_team_code(_team_code(row))]
            real_team_rows = [
                row
                for row in season_rows
                if not is_multi_team_marker(_team_code(row))
                and not is_aggregate_only_team_code(_team_code(row))
            ]

            if tot_rows:
                rows_skipped += len(tot_rows)
                unsupported_rows += len(tot_rows)
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=season_year,
                        source_team_code="TOT",
                        status="skipped",
                        reason="ignored_tot_rows",
                        row_count=len(tot_rows),
                    )
                )

            aggregate_row, reason = _select_full_season_row(season_rows)
            if aggregate_row is None:
                rows_skipped += len(real_team_rows)
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
            else:
                aggregate_team_code = _team_code(aggregate_row)
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=season_year,
                        source_team_code=aggregate_team_code,
                        status="selected",
                        reason=reason,
                        row_count=len(season_rows),
                    )
                )
                selected_rows.append(
                _build_row(
                    row=aggregate_row,
                    league=league,
                    season_year=season_year,
                    source_table=source_table,
                        stat_scope="player_postseason_aggregate",
                    player_id=player_id,
                    source_team_code=aggregate_team_code,
                    team_abbreviation=None,
                )
            )

            for real_team_row in real_team_rows:
                team_code = _team_code(real_team_row)
                selection_entries.append(
                    PlayerPageSelectionEntry(
                        source_table=source_table,
                        season_year=season_year,
                        source_team_code=team_code,
                        status="selected",
                        reason="selected_real_team_postseason_row",
                        row_count=1,
                    )
                )
                selected_rows.append(
                _build_row(
                    row=real_team_row,
                    league=league,
                    season_year=season_year,
                    source_table=source_table,
                        stat_scope="player_team_postseason",
                    player_id=player_id,
                    source_team_code=None,
                    team_abbreviation=team_code,
                )
            )

            if synthetic_rows and aggregate_row is not None and is_multi_team_marker(_team_code(aggregate_row)):
                rows_skipped += max(len(synthetic_rows) - 1, 0)

    return PlayerPageNormalizationResult(
        selected_rows=tuple(selected_rows),
        selection_entries=tuple(selection_entries),
        tables_parsed=tables_parsed,
        rows_selected=len(selected_rows),
        rows_skipped=rows_skipped,
        unsupported_rows=unsupported_rows,
    )


def _normalize_player_page_aggregate_only(
    parsed: Mapping[str, list[dict[str, str]]],
    *,
    basketball_reference_player_id: str,
    league: str,
    start_year: int | None,
    end_year: int | None,
    stat_scope: str,
) -> PlayerPageNormalizationResult:
    player_id = _required_player_id(basketball_reference_player_id)
    selected_rows: list[dict[str, Any]] = []
    selection_entries: list[PlayerPageSelectionEntry] = []
    tables_parsed = 0
    rows_skipped = 0
    unsupported_rows = 0

    for source_table, parsed_rows in parsed.items():
        if parsed_rows:
            tables_parsed += 1

        grouped_rows: dict[int, list[dict[str, str]]] = defaultdict(list)
        invalid_rows = 0
        for parsed_row in parsed_rows:
            season_year = _season_end_year(parsed_row)
            team_code = _team_code(parsed_row)
            if season_year is None or is_aggregate_only_team_code(team_code):
                invalid_rows += 1
                continue
            grouped_rows[season_year].append(parsed_row)

        rows_skipped += invalid_rows
        unsupported_rows += invalid_rows
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
                _build_row(
                    row=selected_row,
                    league=league,
                    season_year=season_year,
                    source_table=source_table,
                    stat_scope=stat_scope,
                    player_id=player_id,
                    source_team_code=source_team_code,
                    team_abbreviation=None,
                )
            )

    return PlayerPageNormalizationResult(
        selected_rows=tuple(selected_rows),
        selection_entries=tuple(selection_entries),
        tables_parsed=tables_parsed,
        rows_selected=len(selected_rows),
        rows_skipped=rows_skipped,
        unsupported_rows=unsupported_rows,
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
    synthetic_rows = [row for row in season_rows if is_multi_team_marker(_team_code(row))]
    if synthetic_rows:
        return synthetic_rows[0], "selected_multi_team_aggregate"

    real_team_rows = [
        row
        for row in season_rows
        if _team_code(row) is not None
        and not _is_did_not_play_placeholder(row)
        and not is_multi_team_marker(_team_code(row))
        and not is_aggregate_only_team_code(_team_code(row))
    ]
    if len(real_team_rows) == 1:
        return real_team_rows[0], "selected_single_team_row"
    if not real_team_rows:
        if any(_is_did_not_play_placeholder(row) for row in season_rows):
            return None, "did_not_play_season"
        return None, "no_supported_team_row"
    return None, "ambiguous_multiple_real_team_rows"


def _is_did_not_play_placeholder(row: Mapping[str, str]) -> bool:
    """Return whether a parsed row is a no-team Did not play placeholder."""

    if _team_code(row) is not None:
        return False
    age = _clean_string(row.get("age"))
    return age is not None and age.startswith(_DID_NOT_PLAY_MARKER)


def _build_row(
    *,
    row: Mapping[str, str],
    league: str,
    season_year: int,
    source_table: str,
    stat_scope: str,
    player_id: str,
    source_team_code: str | None,
    team_abbreviation: str | None,
) -> dict[str, Any]:
    return {
        "league": league,
        "season_year": season_year,
        "source_table": source_table,
        "stat_scope": stat_scope,
        "player_name": _player_name(row),
        "basketball_reference_player_id": player_id,
        "stable_player_key": player_id,
        "identifier_status": "present",
        "source_team_code": source_team_code,
        "team_abbreviation": team_abbreviation,
        "values": _normalized_values(row, source_table=source_table),
    }


def _season_end_year(row: Mapping[str, str]) -> int | None:
    season_value = None
    for key in ("season", "year_id"):
        season_value = _clean_string(row.get(key))
        if season_value is not None:
            break
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

    # A `YYYY-YY` label may cross a century: `1999-00` ends in 2000, not 1900.
    # Roll the century forward by comparison rather than by a hard-coded pivot,
    # so the rule holds for any archive range instead of only this one.
    century = (start_year // 100) * 100
    end_year = century + int(end_suffix)
    if int(end_suffix) < start_year % 100:
        end_year += 100
    return end_year


def _team_code(row: Mapping[str, str]) -> str | None:
    for key in ("team_id", "team_name_abbr", "team_abbreviation", "team", "tm"):
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


def _normalized_values(row: Mapping[str, str], *, source_table: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    excluded_keys = {
        "basketball_reference_player_id",
        "season",
        "year_id",
        "team_id",
        "team_name_abbr",
        "team",
        "tm",
        "team_abbreviation",
        "lg",
        "lg_id",
        "comp_name_abbr",
    }
    if source_table in {"totals", "per_poss"}:
        excluded_keys.add("pos")

    for key, value in row.items():
        normalized_key = _snake_case(key)
        if normalized_key in excluded_keys:
            continue
        values[normalized_key] = _safe_number(value)
    return values


__all__ = [
    "PlayerPageNormalizationResult",
    "PlayerPageSelectionEntry",
    "normalize_player_page_postseason",
    "normalize_player_page_regular_season",
]
