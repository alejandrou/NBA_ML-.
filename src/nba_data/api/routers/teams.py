from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.teams import TeamListResponse, TeamResponse
from nba_data.api.services import teams as team_service

router = APIRouter(prefix="/teams", tags=["teams"])
SessionDependency = Annotated[Session, Depends(get_request_session)]


@router.get(
    "",
    response_model=TeamListResponse,
    summary="List teams",
)
def list_teams(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TeamListResponse:
    return team_service.list_teams(session, page=page, page_size=page_size)


@router.get("/", include_in_schema=False)
def reject_empty_team_code() -> None:
    raise HTTPException(status_code=404, detail="Team not found")


@router.get(
    "/{basketball_reference_team_id}",
    response_model=TeamResponse,
    summary="Get a team",
)
def get_team(
    basketball_reference_team_id: Annotated[str, Path(min_length=1, max_length=10)],
    session: SessionDependency,
) -> TeamResponse:
    team = team_service.get_team(
        session,
        basketball_reference_team_id=basketball_reference_team_id,
    )
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team
