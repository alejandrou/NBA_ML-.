from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from nba_data.db.repositories import CoreRepository
from nba_data.validation.team_season import assert_valid_normalized_team_season_rows


@dataclass(frozen=True)
class TeamSeasonLoadBatch:
    league: str
    season_year: int
    team_abbreviation: str
    rows: list[dict[str, Any]]
    team_name: str | None = None


@dataclass(frozen=True)
class TeamSeasonLoadResult:
    input_rows: int
    player_rows: int
    aggregate_rows: int
    seasons: int
    teams: int
    team_aliases: int
    team_seasons: int
    players: int
    player_seasons: int
    player_team_seasons: int


def load_team_season_core(session: Session, batch: TeamSeasonLoadBatch) -> TeamSeasonLoadResult:
    """Load validated team-season core identities without committing the transaction."""

    normalized_team = _normalize_team_abbreviation(batch.team_abbreviation)
    _validate_before_writes(batch, normalized_team)

    repository = CoreRepository(session)
    season = repository.get_or_create_season(
        league=batch.league,
        season_year=batch.season_year,
    )
    team = repository.get_or_create_team(
        basketball_reference_team_id=normalized_team,
        current_abbreviation=normalized_team,
        current_name=batch.team_name,
    )
    team_alias = repository.get_or_create_team_alias(
        team=team,
        abbreviation=normalized_team,
        name=batch.team_name,
        season_year=batch.season_year,
    )
    team_season = repository.get_or_create_team_season(
        team=team,
        season=season,
        team_abbreviation=normalized_team,
    )

    players = set()
    player_seasons = set()
    player_team_seasons = set()
    player_rows = 0
    aggregate_rows = 0

    for row in batch.rows:
        player_id = _required_string(row.get("basketball_reference_player_id"))
        player_rows += 1
        player = repository.get_or_create_player(
            basketball_reference_player_id=player_id,
            full_name=_optional_string(row.get("player_name")),
        )
        player_season = repository.get_or_create_player_season(player=player, season=season)

        players.add(player.id)
        player_seasons.add(player_season.id)

        if _is_aggregate_row(row):
            aggregate_rows += 1
            continue

        roster_number, roster_position = _roster_values(row)
        player_team_season = repository.get_or_create_player_team_season(
            player_season=player_season,
            team_season=team_season,
            roster_number=roster_number,
            roster_position=roster_position,
        )
        player_team_seasons.add(player_team_season.id)

    return TeamSeasonLoadResult(
        input_rows=len(batch.rows),
        player_rows=player_rows,
        aggregate_rows=aggregate_rows,
        seasons=1,
        teams=1,
        team_aliases=1 if team_alias.id is not None else 0,
        team_seasons=1,
        players=len(players),
        player_seasons=len(player_seasons),
        player_team_seasons=len(player_team_seasons),
    )


def _validate_before_writes(batch: TeamSeasonLoadBatch, normalized_team: str) -> None:
    if normalized_team == "TOT":
        msg = "F4-002 loader cannot load TOT as the batch team."
        raise ValueError(msg)

    assert_valid_normalized_team_season_rows(batch.rows, require_stable_player_id=True)

    for index, row in enumerate(batch.rows):
        row_league = _required_string(row.get("league")).upper()
        row_season_year = row.get("season_year")
        row_team = _normalize_team_abbreviation(row.get("team_abbreviation"))
        team_context = _required_string(row.get("team_context"))
        stat_scope = _required_string(row.get("stat_scope"))

        if row_league != batch.league.upper():
            msg = f"Row {index} league does not match batch league."
            raise ValueError(msg)
        if row_season_year != batch.season_year:
            msg = f"Row {index} season_year does not match batch season_year."
            raise ValueError(msg)
        if row_team == "TOT":
            if team_context != "aggregate" or stat_scope != "player_season_aggregate":
                msg = f"Row {index} has invalid TOT aggregate classification."
                raise ValueError(msg)
            continue
        if team_context == "aggregate" or stat_scope == "player_season_aggregate":
            msg = f"Row {index} aggregate rows must use team_abbreviation TOT."
            raise ValueError(msg)
        if row_team != normalized_team:
            msg = f"Row {index} team_abbreviation does not match batch team."
            raise ValueError(msg)


def _roster_values(row: dict[str, Any]) -> tuple[str | None, str | None]:
    if row.get("source_table") != "roster":
        return None, None

    values = row.get("values")
    if not isinstance(values, dict):
        return None, None

    return _optional_string(values.get("number")), _optional_string(values.get("pos"))


def _is_aggregate_row(row: dict[str, Any]) -> bool:
    return (
        _normalize_team_abbreviation(row.get("team_abbreviation")) == "TOT"
        or row.get("team_context") == "aggregate"
        or row.get("stat_scope") == "player_season_aggregate"
    )


def _normalize_team_abbreviation(value: object) -> str:
    return _required_string(value).upper()


def _required_string(value: object) -> str:
    cleaned = _optional_string(value)
    if cleaned is None:
        msg = "Expected a non-empty string."
        raise ValueError(msg)
    return cleaned


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
