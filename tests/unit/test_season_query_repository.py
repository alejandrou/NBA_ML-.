from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.db.models.core import Season
from nba_data.db.repositories.queries.seasons import count_seasons, get_season, list_seasons


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        Season.__table__.create(connection)
        with Session(bind=connection) as session:
            session.add_all(
                [
                    Season(id=1, season_year=2023, league="NBA", label="2023"),
                    Season(id=3, season_year=2025, league="NBA", label=None),
                    Season(id=2, season_year=2024, league="NBA", label="2024"),
                    Season(id=4, season_year=1975, league="ABA", label="1975"),
                ]
            )
            session.commit()
            yield session
    engine.dispose()


@pytest.mark.unit
def test_season_queries_count_order_and_paginate(session: Session) -> None:
    assert count_seasons(session) == 3

    seasons = list_seasons(session, offset=0, limit=2)

    assert [season.season_year for season in seasons] == [2025, 2024]
    assert [season.season_year for season in list_seasons(session, offset=2, limit=2)] == [2023]
    assert list_seasons(session, offset=3, limit=2) == []


@pytest.mark.unit
def test_season_queries_expose_only_the_nba_league(session: Session) -> None:
    seasons = list_seasons(session, offset=0, limit=100)

    assert {season.league for season in seasons} == {"NBA"}
    assert get_season(session, 1975) is None


@pytest.mark.unit
def test_season_query_get_returns_season_or_none(session: Session) -> None:
    season = get_season(session, 2024)

    assert season is not None
    assert season.season_year == 2024
    assert season.label == "2024"
    assert get_season(session, 1800) is None
