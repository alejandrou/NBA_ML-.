from __future__ import annotations

from typing import Any

PLAYER_NAME_FIELDS = ("player", "Player", "name_display")


def normalize_team_season_page(
    parsed: dict[str, list[dict[str, str]]],
    *,
    team_abbreviation: str,
    season_year: int,
    league: str = "NBA",
) -> list[dict[str, Any]]:
    """Normalize parsed team-season tables without loading or generating metrics."""

    team = team_abbreviation.strip().upper()
    rows: list[dict[str, Any]] = []

    for source_table, parsed_rows in parsed.items():
        for parsed_row in parsed_rows:
            player_id = _clean_string(parsed_row.get("basketball_reference_player_id"))
            player_name = _player_name(parsed_row)
            row_team = _row_team_abbreviation(parsed_row, team)
            team_context = "aggregate" if row_team == "TOT" else "team"

            rows.append(
                {
                    "league": league,
                    "season_year": season_year,
                    "team_abbreviation": row_team,
                    "team_context": team_context,
                    "source_table": source_table,
                    "stat_scope": _stat_scope(source_table, team_context),
                    "player_name": player_name,
                    "basketball_reference_player_id": player_id,
                    "stable_player_key": player_id,
                    "identifier_status": "present" if player_id else "missing_player_id",
                    "values": _normalized_values(parsed_row),
                }
            )

    return rows


def _row_team_abbreviation(row: dict[str, str], page_team: str) -> str:
    for key in ("team_abbreviation", "team_id", "team", "tm"):
        value = _clean_string(row.get(key))
        if value:
            return value.upper()
    return page_team


def _stat_scope(source_table: str, team_context: str) -> str:
    if team_context == "aggregate":
        return "player_season_aggregate"
    if source_table == "roster":
        return "team_roster"
    return "player_team_season"


def _player_name(row: dict[str, str]) -> str | None:
    for field in PLAYER_NAME_FIELDS:
        value = _clean_string(row.get(field))
        if value:
            return value
    return None


def _normalized_values(row: dict[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in row.items():
        normalized_key = _snake_case(key)
        if normalized_key == "basketball_reference_player_id":
            continue
        values[normalized_key] = _safe_number(value)
    return values


def _safe_number(value: str) -> Any:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None

    if cleaned.startswith("$"):
        return cleaned

    number = cleaned.replace(",", "")
    if number.startswith("."):
        number = f"0{number}"
    elif number.startswith("-."):
        number = number.replace("-.", "-0.", 1)

    if number.removeprefix("-").isdigit():
        return int(number)

    try:
        return float(number)
    except ValueError:
        return cleaned


def _clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _snake_case(value: str) -> str:
    normalized = value.strip().replace("%", "pct")
    chars: list[str] = []
    previous_was_separator = False

    for char in normalized:
        if char.isalnum():
            chars.append(char.lower())
            previous_was_separator = False
        elif not previous_was_separator:
            chars.append("_")
            previous_was_separator = True

    return "".join(chars).strip("_")
