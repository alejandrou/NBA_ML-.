from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.seasons import SeasonListResponse, SeasonResponse
from nba_data.api.services import seasons as season_service

router = APIRouter(prefix="/seasons", tags=["seasons"])
SessionDependency = Annotated[Session, Depends(get_request_session)]


@router.get(
    "",
    response_model=SeasonListResponse,
    summary="List seasons",
)
def list_seasons(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SeasonListResponse:
    return season_service.list_seasons(session, page=page, page_size=page_size)


@router.get(
    "/{season_year}",
    response_model=SeasonResponse,
    summary="Get a season",
)
def get_season(
    season_year: Annotated[int, Path(ge=1)],
    session: SessionDependency,
) -> SeasonResponse:
    season = season_service.get_season(session, season_year=season_year)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    return season
