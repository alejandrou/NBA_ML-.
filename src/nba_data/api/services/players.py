from sqlalchemy.orm import Session

from nba_data.api.schemas.players import (
    PlayerListResponse,
    PlayerResponse,
    PlayerSeasonListResponse,
    PlayerSeasonResponse,
)
from nba_data.db.models.core import Player
from nba_data.db.repositories.queries import players as player_queries
from nba_data.db.repositories.queries.players import PlayerSeasonIdentity


class PlayerNotFoundError(Exception):
    """No publishable player has the requested Basketball Reference id."""


class PlayerSeasonNotFoundError(Exception):
    """The player exists but has no NBA season with the requested year."""


def list_players(session: Session, *, page: int, page_size: int) -> PlayerListResponse:
    """List players and map ORM entities to the approved public contract."""
    offset = (page - 1) * page_size
    total = player_queries.count_players(session)
    players = player_queries.list_players(session, offset=offset, limit=page_size)

    return PlayerListResponse(
        items=[_to_player_response(player) for player in players],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_player(session: Session, *, basketball_reference_player_id: str) -> PlayerResponse:
    """Return one mapped player, or raise `PlayerNotFoundError`."""
    return _to_player_response(_require_player(session, basketball_reference_player_id))


def list_player_seasons(
    session: Session,
    *,
    basketball_reference_player_id: str,
    page: int,
    page_size: int,
) -> PlayerSeasonListResponse:
    """List a known player's NBA seasons; a player with none yields an empty page."""
    _require_player(session, basketball_reference_player_id)

    offset = (page - 1) * page_size
    total = player_queries.count_player_seasons(session, basketball_reference_player_id)
    seasons = player_queries.list_player_seasons(
        session,
        basketball_reference_player_id,
        offset=offset,
        limit=page_size,
    )

    return PlayerSeasonListResponse(
        items=[_to_season_response(season) for season in seasons],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_player_season(
    session: Session,
    *,
    basketball_reference_player_id: str,
    season_year: int,
) -> PlayerSeasonResponse:
    """Return one season of a known player, or raise the error naming what is missing."""
    _require_player(session, basketball_reference_player_id)

    season = player_queries.get_player_season(
        session,
        basketball_reference_player_id,
        season_year,
    )
    if season is None:
        raise PlayerSeasonNotFoundError
    return _to_season_response(season)


def _require_player(session: Session, basketball_reference_player_id: str) -> Player:
    player = player_queries.get_player(session, basketball_reference_player_id)
    if player is None:
        raise PlayerNotFoundError
    return player


def _to_player_response(player: Player) -> PlayerResponse:
    # Every query that yields a player filters on the id, so a null here is a
    # defect in that layer. Failing loudly beats serving a null public key.
    if player.basketball_reference_player_id is None:
        raise ValueError("a player without a Basketball Reference id reached the API")
    return PlayerResponse(
        basketball_reference_player_id=player.basketball_reference_player_id,
        full_name=player.full_name,
    )


def _to_season_response(season: PlayerSeasonIdentity) -> PlayerSeasonResponse:
    return PlayerSeasonResponse(
        season_year=season.season_year,
        league=season.league,
        teams=list(season.teams),
    )
