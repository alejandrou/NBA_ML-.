from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.players import (
    PlayerListResponse,
    PlayerResponse,
    PlayerSeasonListResponse,
    PlayerSeasonResponse,
)
from nba_data.api.services import players as player_service
from nba_data.api.services.players import PlayerNotFoundError, PlayerSeasonNotFoundError

router = APIRouter(prefix="/players", tags=["players"])
SessionDependency = Annotated[Session, Depends(get_request_session)]
PlayerIdPath = Annotated[str, Path(min_length=1, max_length=32)]
SeasonYearPath = Annotated[int, Path(ge=1)]

# Fixed strings: they never interpolate the id, the year, or an exception.
PLAYER_NOT_FOUND = "Player not found"
PLAYER_SEASON_NOT_FOUND = "Player season not found"


@router.get(
    "",
    response_model=PlayerListResponse,
    summary="List players",
)
def list_players(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PlayerListResponse:
    return player_service.list_players(session, page=page, page_size=page_size)


@router.get("/", include_in_schema=False)
def reject_empty_player_id() -> None:
    raise HTTPException(status_code=404, detail=PLAYER_NOT_FOUND)


@router.get(
    "/{basketball_reference_player_id}",
    response_model=PlayerResponse,
    summary="Get a player",
)
def get_player(
    basketball_reference_player_id: PlayerIdPath,
    session: SessionDependency,
) -> PlayerResponse:
    try:
        return player_service.get_player(
            session,
            basketball_reference_player_id=basketball_reference_player_id,
        )
    except PlayerNotFoundError:
        raise HTTPException(status_code=404, detail=PLAYER_NOT_FOUND) from None


@router.get(
    "/{basketball_reference_player_id}/seasons",
    response_model=PlayerSeasonListResponse,
    summary="List a player's seasons",
)
def list_player_seasons(
    basketball_reference_player_id: PlayerIdPath,
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PlayerSeasonListResponse:
    try:
        return player_service.list_player_seasons(
            session,
            basketball_reference_player_id=basketball_reference_player_id,
            page=page,
            page_size=page_size,
        )
    except PlayerNotFoundError:
        raise HTTPException(status_code=404, detail=PLAYER_NOT_FOUND) from None


@router.get(
    "/{basketball_reference_player_id}/seasons/{season_year}",
    response_model=PlayerSeasonResponse,
    summary="Get a player's season",
)
def get_player_season(
    basketball_reference_player_id: PlayerIdPath,
    season_year: SeasonYearPath,
    session: SessionDependency,
) -> PlayerSeasonResponse:
    try:
        return player_service.get_player_season(
            session,
            basketball_reference_player_id=basketball_reference_player_id,
            season_year=season_year,
        )
    except PlayerNotFoundError:
        raise HTTPException(status_code=404, detail=PLAYER_NOT_FOUND) from None
    except PlayerSeasonNotFoundError:
        raise HTTPException(status_code=404, detail=PLAYER_SEASON_NOT_FOUND) from None
