from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Row, Select, func, select
from sqlalchemy.orm import Session

from nba_data.db.models.core import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamSeason,
)
from nba_data.db.repositories.queries.seasons import NBA_LEAGUE


@dataclass(frozen=True)
class PlayerSeasonIdentity:
    """One NBA season of a player, with the team codes of its stints."""

    season_year: int
    league: str
    teams: tuple[str, ...]


def list_players(session: Session, *, offset: int, limit: int) -> list[Player]:
    """Return one deterministic page of publishable players without changing the Session."""
    statement = (
        select(Player)
        .where(Player.basketball_reference_player_id.is_not(None))
        .order_by(
            Player.full_name.asc(),
            Player.basketball_reference_player_id.asc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def count_players(session: Session) -> int:
    """Return the number of publishable players without changing the Session."""
    statement = (
        select(func.count())
        .select_from(Player)
        .where(Player.basketball_reference_player_id.is_not(None))
    )
    return int(session.scalar(statement) or 0)


def get_player(session: Session, basketball_reference_player_id: str) -> Player | None:
    """Return one player by its exact Basketball Reference id, if it exists."""
    statement = select(Player).where(
        Player.basketball_reference_player_id == basketball_reference_player_id
    )
    return session.scalar(statement)


def list_player_seasons(
    session: Session,
    basketball_reference_player_id: str,
    *,
    offset: int,
    limit: int,
) -> list[PlayerSeasonIdentity]:
    """Return one page of a player's NBA seasons, newest first, with their teams."""
    statement = (
        _player_seasons(basketball_reference_player_id)
        .order_by(Season.season_year.desc())
        .offset(offset)
        .limit(limit)
    )
    return _with_teams(session, session.execute(statement).all())


def count_player_seasons(session: Session, basketball_reference_player_id: str) -> int:
    """Return the number of a player's NBA seasons without changing the Session."""
    statement = select(func.count()).select_from(
        _player_seasons(basketball_reference_player_id).subquery()
    )
    return int(session.scalar(statement) or 0)


def get_player_season(
    session: Session,
    basketball_reference_player_id: str,
    season_year: int,
) -> PlayerSeasonIdentity | None:
    """Return one NBA season of a player by its public year, if it exists."""
    statement = _player_seasons(basketball_reference_player_id).where(
        Season.season_year == season_year
    )
    seasons = _with_teams(session, session.execute(statement).all())
    return seasons[0] if seasons else None


def _player_seasons(basketball_reference_player_id: str) -> Select[tuple[int, int, str]]:
    return (
        select(PlayerSeason.id, Season.season_year, Season.league)
        .join(Season, PlayerSeason.season_id == Season.id)
        .join(Player, PlayerSeason.player_id == Player.id)
        .where(
            Player.basketball_reference_player_id == basketball_reference_player_id,
            Season.league == NBA_LEAGUE,
        )
    )


def _with_teams(
    session: Session,
    rows: Sequence[Row[tuple[int, int, str]]],
) -> list[PlayerSeasonIdentity]:
    """Attach the team codes of every row with one query for the page, never one per row."""
    teams: defaultdict[int, list[str]] = defaultdict(list)
    player_season_ids = [row.id for row in rows]
    if player_season_ids:
        statement = (
            select(PlayerTeamSeason.player_season_id, Team.basketball_reference_team_id)
            .join(TeamSeason, PlayerTeamSeason.team_season_id == TeamSeason.id)
            .join(Team, TeamSeason.team_id == Team.id)
            .where(PlayerTeamSeason.player_season_id.in_(player_season_ids))
            .order_by(Team.basketball_reference_team_id.asc())
        )
        for player_season_id, team_code in session.execute(statement):
            teams[player_season_id].append(team_code)

    return [
        PlayerSeasonIdentity(
            season_year=row.season_year,
            league=row.league,
            teams=tuple(teams[row.id]),
        )
        for row in rows
    ]
