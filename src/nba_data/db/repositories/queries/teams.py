from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nba_data.db.models.core import Team


def list_teams(session: Session, *, offset: int, limit: int) -> list[Team]:
    """Return one deterministic page of teams without changing the Session."""
    statement = (
        select(Team)
        .order_by(Team.current_name.asc(), Team.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def count_teams(session: Session) -> int:
    """Return the total number of teams without changing the Session."""
    statement = select(func.count()).select_from(Team)
    return int(session.scalar(statement) or 0)


def get_team(session: Session, team_id: int) -> Team | None:
    """Return one team by its stable internal identifier, if it exists."""
    statement = select(Team).where(Team.id == team_id)
    return session.scalar(statement)
