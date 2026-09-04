from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nba_data.db.models.core import Season

NBA_LEAGUE = "NBA"


def list_seasons(session: Session, *, offset: int, limit: int) -> list[Season]:
    """Return one deterministic page of NBA seasons without changing the Session."""
    statement = (
        select(Season)
        .where(Season.league == NBA_LEAGUE)
        .order_by(Season.season_year.desc(), Season.league.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def count_seasons(session: Session) -> int:
    """Return the total number of NBA seasons without changing the Session."""
    statement = select(func.count()).select_from(Season).where(Season.league == NBA_LEAGUE)
    return int(session.scalar(statement) or 0)


def get_season_years(session: Session) -> frozenset[int]:
    """Return the NBA season years currently present in ``core.seasons``."""
    statement = select(Season.season_year).where(Season.league == NBA_LEAGUE)
    return frozenset(int(season_year) for season_year in session.scalars(statement))


def get_season(session: Session, season_year: int) -> Season | None:
    """Return one NBA season by its public year, if it exists."""
    statement = select(Season).where(
        Season.league == NBA_LEAGUE,
        Season.season_year == season_year,
    )
    return session.scalars(statement).one_or_none()
