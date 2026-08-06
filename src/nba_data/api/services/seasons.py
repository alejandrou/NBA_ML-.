from sqlalchemy.orm import Session

from nba_data.api.schemas.seasons import SeasonListResponse, SeasonResponse
from nba_data.db.models.core import Season
from nba_data.db.repositories.queries import seasons as season_queries


def list_seasons(session: Session, *, page: int, page_size: int) -> SeasonListResponse:
    """List seasons and map ORM entities to the approved public contract."""
    offset = (page - 1) * page_size
    total = season_queries.count_seasons(session)
    seasons = season_queries.list_seasons(session, offset=offset, limit=page_size)

    return SeasonListResponse(
        items=[_to_response(season) for season in seasons],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_season(session: Session, *, season_year: int) -> SeasonResponse | None:
    """Return one mapped season, or None when the public year is missing."""
    season = season_queries.get_season(session, season_year)
    return _to_response(season) if season is not None else None


def _to_response(season: Season) -> SeasonResponse:
    return SeasonResponse(
        season_year=season.season_year,
        league=season.league,
        label=season.label,
    )
