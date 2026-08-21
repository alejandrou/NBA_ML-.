from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nba_data.db.models.core import Team


def list_teams(session: Session, *, offset: int, limit: int) -> list[Team]:
    """Return one deterministic page of teams without changing the Session."""
    statement = (
        select(Team)
        .order_by(
            Team.current_name.asc(),
            Team.basketball_reference_team_id.asc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def count_teams(session: Session) -> int:
    """Return the total number of teams without changing the Session."""
    statement = select(func.count()).select_from(Team)
    return int(session.scalar(statement) or 0)


def get_team_by_basketball_reference_team_id(
    session: Session,
    basketball_reference_team_id: str,
) -> Team | None:
    """Return one team by its exact Basketball Reference code, if it exists."""
    statement = select(Team).where(
        Team.basketball_reference_team_id == basketball_reference_team_id
    )
    return session.scalar(statement)
