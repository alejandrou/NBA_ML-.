from typing import Any, cast

from sqlalchemy import Table
from sqlalchemy.orm import Session

from nba_data.api.schemas.player_stats import (
    STAT_BODIES,
    AggregateStatIdentity,
    StintStatListResponse,
)
from nba_data.api.services.players import PlayerNotFoundError, PlayerSeasonNotFoundError
from nba_data.db.repositories.queries import player_stats as stat_queries
from nba_data.db.repositories.queries import players as player_queries
from nba_data.domain.stat_dimensions import SeasonType, StatFamily
from nba_data.domain.team_codes import is_multi_team_marker

# Postseason joins in F6-014; the table maps already name both season types.
SERVED_SEASON_TYPES: tuple[SeasonType, ...] = (SeasonType.REGULAR,)


class StatisticsNotFoundError(Exception):
    """The player-season exists but stores no aggregate row in that dimension and family."""


def served_stat_tables() -> tuple[str, ...]:
    """Return the schema-qualified stat tables the served routes read."""
    return tuple(
        cast(Table, table.__table__).fullname
        for tables in (stat_queries.AGGREGATE_TABLES, stat_queries.STINT_TABLES)
        for season_type in SERVED_SEASON_TYPES
        for table in tables[season_type].values()
    )


def get_aggregate_stats(
    session: Session,
    *,
    basketball_reference_player_id: str,
    season_year: int,
    season_type: SeasonType,
    family: StatFamily,
) -> AggregateStatIdentity:
    """Return one player-season's aggregate row, or raise the error naming what is missing."""
    player_season_id = _require_player_season(session, basketball_reference_player_id, season_year)

    table = stat_queries.AGGREGATE_TABLES[season_type][family]
    row = stat_queries.get_aggregate_stats(session, table, player_season_id)
    if row is None:
        raise StatisticsNotFoundError

    body, _ = STAT_BODIES[family]
    return body.model_validate(
        {
            **row,
            "season_year": season_year,
            "season_type": season_type,
            "is_multi_team": is_multi_team_marker(row["source_team_code"]),
        }
    )


def list_stint_stats(
    session: Session,
    *,
    basketball_reference_player_id: str,
    season_year: int,
    season_type: SeasonType,
    family: StatFamily,
    page: int,
    page_size: int,
) -> StintStatListResponse[Any]:
    """List one player-season's stint rows; a season with none yields an empty page."""
    player_season_id = _require_player_season(session, basketball_reference_player_id, season_year)

    table = stat_queries.STINT_TABLES[season_type][family]
    offset = (page - 1) * page_size
    total = stat_queries.count_stint_stats(session, table, player_season_id)
    rows = stat_queries.list_stint_stats(
        session,
        table,
        player_season_id,
        offset=offset,
        limit=page_size,
    )

    _, body = STAT_BODIES[family]
    return body.model_validate(
        {
            "items": [
                {**row, "season_year": season_year, "season_type": season_type} for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )


def _require_player_season(
    session: Session,
    basketball_reference_player_id: str,
    season_year: int,
) -> int:
    if player_queries.get_player(session, basketball_reference_player_id) is None:
        raise PlayerNotFoundError
    player_season_id = stat_queries.get_player_season_id(
        session,
        basketball_reference_player_id,
        season_year,
    )
    if player_season_id is None:
        raise PlayerSeasonNotFoundError
    return player_season_id
