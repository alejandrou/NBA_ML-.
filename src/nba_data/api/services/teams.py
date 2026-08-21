from sqlalchemy.orm import Session

from nba_data.api.schemas.teams import TeamListResponse, TeamResponse
from nba_data.db.models.core import Team
from nba_data.db.repositories.queries import teams as team_queries


def list_teams(session: Session, *, page: int, page_size: int) -> TeamListResponse:
    """List teams and map ORM entities to the approved public contract."""
    offset = (page - 1) * page_size
    total = team_queries.count_teams(session)
    teams = team_queries.list_teams(session, offset=offset, limit=page_size)

    return TeamListResponse(
        items=[_to_response(team) for team in teams],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_team(
    session: Session,
    *,
    basketball_reference_team_id: str,
) -> TeamResponse | None:
    """Return one mapped team, or None when the identifier is missing."""
    team = team_queries.get_team_by_basketball_reference_team_id(
        session,
        basketball_reference_team_id,
    )
    return _to_response(team) if team is not None else None


def _to_response(team: Team) -> TeamResponse:
    return TeamResponse(
        basketball_reference_team_id=team.basketball_reference_team_id,
        current_abbreviation=team.current_abbreviation,
        current_name=team.current_name,
    )
