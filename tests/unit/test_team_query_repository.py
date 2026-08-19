from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from nba_data.db.models.core import Team
from nba_data.db.repositories.queries.teams import (
    count_teams,
    get_team_by_basketball_reference_team_id,
    list_teams,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        Team.__table__.create(connection)
        with Session(bind=connection) as session:
            session.add_all(
                [
                    Team(
                        id=3,
                        basketball_reference_team_id="AAA",
                        current_abbreviation="AAA",
                        current_name="Bulls",
                    ),
                    Team(
                        id=1,
                        basketball_reference_team_id="BBB",
                        current_abbreviation="BBB",
                        current_name="Bulls",
                    ),
                    Team(
                        id=2,
                        basketball_reference_team_id="CCC",
                        current_abbreviation=None,
                        current_name="Celtics",
                    ),
                ]
            )
            session.commit()
            yield session
    engine.dispose()


@pytest.mark.unit
def test_team_queries_count_order_and_paginate(session: Session) -> None:
    assert count_teams(session) == 3

    teams = list_teams(session, offset=0, limit=2)

    assert [(team.basketball_reference_team_id, team.current_name) for team in teams] == [
        ("AAA", "Bulls"),
        ("BBB", "Bulls"),
    ]
    assert [team.id for team in list_teams(session, offset=2, limit=2)] == [2]
    assert list_teams(session, offset=3, limit=2) == []


@pytest.mark.unit
def test_team_query_get_returns_team_or_none(session: Session) -> None:
    team = get_team_by_basketball_reference_team_id(session, "CCC")

    assert team is not None
    assert team.current_name == "Celtics"
    assert get_team_by_basketball_reference_team_id(session, "ccc") is None
    assert get_team_by_basketball_reference_team_id(session, "UNKNOWN") is None
