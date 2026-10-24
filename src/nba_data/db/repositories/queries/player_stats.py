"""Read-only queries for one player-season's official statistics.

One map per grain names the table of every family in both season types, so a
season type is served by registering its routes, never by editing this module.
"""

from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from nba_data.db.base import Base
from nba_data.db.models.core import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamSeason,
)
from nba_data.db.models.stats import (
    PlayerPostseasonAdjShooting,
    PlayerPostseasonAdvanced,
    PlayerPostseasonPbp,
    PlayerPostseasonPerGame,
    PlayerPostseasonPerMinute,
    PlayerPostseasonPerPoss,
    PlayerPostseasonShooting,
    PlayerPostseasonTotals,
    PlayerSeasonAdjShooting,
    PlayerSeasonAdvanced,
    PlayerSeasonPbp,
    PlayerSeasonPerGame,
    PlayerSeasonPerMinute,
    PlayerSeasonPerPoss,
    PlayerSeasonShooting,
    PlayerSeasonTotals,
    PlayerTeamPostseasonAdjShooting,
    PlayerTeamPostseasonAdvanced,
    PlayerTeamPostseasonPbp,
    PlayerTeamPostseasonPerGame,
    PlayerTeamPostseasonPerMinute,
    PlayerTeamPostseasonPerPoss,
    PlayerTeamPostseasonShooting,
    PlayerTeamPostseasonTotals,
    PlayerTeamSeasonAdjShooting,
    PlayerTeamSeasonAdvanced,
    PlayerTeamSeasonPbp,
    PlayerTeamSeasonPerGame,
    PlayerTeamSeasonPerMinute,
    PlayerTeamSeasonPerPoss,
    PlayerTeamSeasonShooting,
    PlayerTeamSeasonTotals,
)
from nba_data.db.repositories.queries.seasons import NBA_LEAGUE
from nba_data.domain.stat_dimensions import SeasonType, StatFamily

AGGREGATE_TABLES: dict[SeasonType, dict[StatFamily, type[Base]]] = {
    SeasonType.REGULAR: {
        StatFamily.TOTALS: PlayerSeasonTotals,
        StatFamily.PER_GAME: PlayerSeasonPerGame,
        StatFamily.PER_MINUTE: PlayerSeasonPerMinute,
        StatFamily.PER_POSS: PlayerSeasonPerPoss,
        StatFamily.ADVANCED: PlayerSeasonAdvanced,
        StatFamily.SHOOTING: PlayerSeasonShooting,
        StatFamily.ADJ_SHOOTING: PlayerSeasonAdjShooting,
        StatFamily.PBP: PlayerSeasonPbp,
    },
    SeasonType.POSTSEASON: {
        StatFamily.TOTALS: PlayerPostseasonTotals,
        StatFamily.PER_GAME: PlayerPostseasonPerGame,
        StatFamily.PER_MINUTE: PlayerPostseasonPerMinute,
        StatFamily.PER_POSS: PlayerPostseasonPerPoss,
        StatFamily.ADVANCED: PlayerPostseasonAdvanced,
        StatFamily.SHOOTING: PlayerPostseasonShooting,
        StatFamily.ADJ_SHOOTING: PlayerPostseasonAdjShooting,
        StatFamily.PBP: PlayerPostseasonPbp,
    },
}

STINT_TABLES: dict[SeasonType, dict[StatFamily, type[Base]]] = {
    SeasonType.REGULAR: {
        StatFamily.TOTALS: PlayerTeamSeasonTotals,
        StatFamily.PER_GAME: PlayerTeamSeasonPerGame,
        StatFamily.PER_MINUTE: PlayerTeamSeasonPerMinute,
        StatFamily.PER_POSS: PlayerTeamSeasonPerPoss,
        StatFamily.ADVANCED: PlayerTeamSeasonAdvanced,
        StatFamily.SHOOTING: PlayerTeamSeasonShooting,
        StatFamily.ADJ_SHOOTING: PlayerTeamSeasonAdjShooting,
        StatFamily.PBP: PlayerTeamSeasonPbp,
    },
    SeasonType.POSTSEASON: {
        StatFamily.TOTALS: PlayerTeamPostseasonTotals,
        StatFamily.PER_GAME: PlayerTeamPostseasonPerGame,
        StatFamily.PER_MINUTE: PlayerTeamPostseasonPerMinute,
        StatFamily.PER_POSS: PlayerTeamPostseasonPerPoss,
        StatFamily.ADVANCED: PlayerTeamPostseasonAdvanced,
        StatFamily.SHOOTING: PlayerTeamPostseasonShooting,
        StatFamily.ADJ_SHOOTING: PlayerTeamPostseasonAdjShooting,
        StatFamily.PBP: PlayerTeamPostseasonPbp,
    },
}

# Keys and lineage stay private (API_CONTRACT.md); `player_name_display` is a
# named v1 non-promise. Everything else a stat table stores is published.
UNPUBLISHED_COLUMNS = frozenset(
    {
        "id",
        "player_season_id",
        "player_team_season_id",
        "player_name_display",
        "source_url",
        "cache_path",
        "parser_version",
        "created_at",
        "updated_at",
    }
)


def get_player_season_id(
    session: Session,
    basketball_reference_player_id: str,
    season_year: int,
) -> int | None:
    """Return the private id of one NBA season of a player, if it exists."""
    statement = (
        select(PlayerSeason.id)
        .join(Season, PlayerSeason.season_id == Season.id)
        .join(Player, PlayerSeason.player_id == Player.id)
        .where(
            Player.basketball_reference_player_id == basketball_reference_player_id,
            Season.season_year == season_year,
            Season.league == NBA_LEAGUE,
        )
    )
    return session.scalar(statement)


def get_aggregate_stats(
    session: Session,
    table: type[Base],
    player_season_id: int,
) -> dict[str, Any] | None:
    """Return the published columns of a player-season's one aggregate row, if stored."""
    statement = select(*_published_columns(table)).where(
        table.__table__.c.player_season_id == player_season_id
    )
    row = session.execute(statement).mappings().first()
    return dict(row) if row is not None else None


def list_stint_stats(
    session: Session,
    table: type[Base],
    player_season_id: int,
    *,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return one page of a player-season's stint rows, ordered by team code."""
    statement = (
        _stint_rows(table, player_season_id)
        .add_columns(*_published_columns(table))
        .order_by(Team.basketball_reference_team_id.asc(), table.__table__.c.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return [dict(row) for row in session.execute(statement).mappings()]


def count_stint_stats(session: Session, table: type[Base], player_season_id: int) -> int:
    """Return the number of a player-season's stint rows without changing the Session."""
    statement = select(func.count()).select_from(_stint_rows(table, player_season_id).subquery())
    return int(session.scalar(statement) or 0)


def _stint_rows(table: type[Base], player_season_id: int) -> Select[Any]:
    columns = table.__table__.c
    return (
        select(Team.basketball_reference_team_id)
        .select_from(table)
        .join(PlayerTeamSeason, columns.player_team_season_id == PlayerTeamSeason.id)
        .join(TeamSeason, PlayerTeamSeason.team_season_id == TeamSeason.id)
        .join(Team, TeamSeason.team_id == Team.id)
        .where(PlayerTeamSeason.player_season_id == player_season_id)
    )


def _published_columns(table: type[Base]) -> list[ColumnElement[Any]]:
    return [column for column in table.__table__.columns if column.name not in UNPUBLISHED_COLUMNS]
