from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from nba_data.db.models.core import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamSeason,
)
from nba_data.db.repositories.queries.players import (
    PlayerSeasonIdentity,
    count_player_seasons,
    count_players,
    get_player,
    get_player_season,
    list_player_seasons,
    list_players,
)

CORE_TABLES = (Season, Team, Player, TeamSeason, PlayerSeason, PlayerTeamSeason)


class StatementLog:
    """Every SQL statement the connection runs, so tests can count and classify them."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def __call__(self, conn: object, cursor: object, statement: str, *args: object) -> None:
        self.statements.append(statement)


@pytest.fixture
def statements() -> StatementLog:
    return StatementLog()


@pytest.fixture
def session(statements: StatementLog) -> Iterator[Session]:
    """Surrogate ids are deliberately out of natural-key order throughout.

    `smithjo01` sits at id 3 and `smithjo02` at id 2, and the 2004 stints are
    inserted `MIA` before `CLE`, so an ordering that leaned on insertion or on a
    surrogate would put the wrong row first.
    """
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        for model in CORE_TABLES:
            model.__table__.create(connection)  # type: ignore[attr-defined]
        with Session(bind=connection) as session:
            session.add_all(
                [
                    Season(id=1, season_year=2003, league="NBA", label="2003"),
                    Season(id=2, season_year=2004, league="NBA", label="2004"),
                    Season(id=3, season_year=2005, league="NBA", label="2005"),
                    Season(id=4, season_year=2004, league="ABA", label="2004"),
                    Team(id=1, basketball_reference_team_id="CLE", current_name="Cavaliers"),
                    Team(id=2, basketball_reference_team_id="MIA", current_name="Heat"),
                    Team(id=3, basketball_reference_team_id="ATL", current_name="Hawks"),
                    TeamSeason(id=1, team_id=1, season_id=1, team_abbreviation="CLE"),
                    TeamSeason(id=2, team_id=1, season_id=2, team_abbreviation="CLE"),
                    TeamSeason(id=3, team_id=2, season_id=2, team_abbreviation="MIA"),
                    TeamSeason(id=4, team_id=3, season_id=4, team_abbreviation="ATL"),
                    Player(
                        id=5, basketball_reference_player_id="jamesle01", full_name="LeBron James"
                    ),
                    Player(
                        id=3, basketball_reference_player_id="smithjo01", full_name="John Smith"
                    ),
                    Player(
                        id=2, basketball_reference_player_id="smithjo02", full_name="John Smith"
                    ),
                    Player(
                        id=6, basketball_reference_player_id="rookiaa01", full_name="Aaron Rookie"
                    ),
                    Player(id=1, basketball_reference_player_id=None, full_name="Aaron Aardvark"),
                    PlayerSeason(id=10, player_id=5, season_id=1),
                    PlayerSeason(id=11, player_id=5, season_id=2),
                    PlayerSeason(id=12, player_id=5, season_id=3),
                    PlayerSeason(id=13, player_id=5, season_id=4),
                    PlayerSeason(id=14, player_id=3, season_id=1),
                    PlayerTeamSeason(id=1, player_season_id=10, team_season_id=1),
                    PlayerTeamSeason(id=2, player_season_id=11, team_season_id=3),
                    PlayerTeamSeason(id=3, player_season_id=11, team_season_id=2),
                    PlayerTeamSeason(id=4, player_season_id=13, team_season_id=4),
                    PlayerTeamSeason(id=5, player_season_id=14, team_season_id=1),
                ]
            )
            session.commit()
            session.expunge_all()
            event.listen(connection, "before_cursor_execute", statements)
            yield session
    engine.dispose()


@pytest.mark.unit
def test_player_queries_exclude_null_ids_and_order_by_name_then_natural_key(
    session: Session,
) -> None:
    """`Aaron Aardvark` would sort first; it has no id and must not be counted or listed."""
    assert count_players(session) == 4

    listed = list_players(session, offset=0, limit=100)

    assert [(player.full_name, player.basketball_reference_player_id) for player in listed] == [
        ("Aaron Rookie", "rookiaa01"),
        ("John Smith", "smithjo01"),
        ("John Smith", "smithjo02"),
        ("LeBron James", "jamesle01"),
    ]


@pytest.mark.unit
def test_player_queries_paginate_without_repeating_a_player(session: Session) -> None:
    pages = [list_players(session, offset=offset, limit=2) for offset in (0, 2, 4)]

    assert [[player.basketball_reference_player_id for player in page] for page in pages] == [
        ["rookiaa01", "smithjo01"],
        ["smithjo02", "jamesle01"],
        [],
    ]


@pytest.mark.unit
def test_get_player_matches_the_id_exactly(session: Session) -> None:
    player = get_player(session, "jamesle01")

    assert player is not None
    assert player.full_name == "LeBron James"
    assert get_player(session, "JAMESLE01") is None
    assert get_player(session, "5") is None
    assert get_player(session, "unknown01") is None


@pytest.mark.unit
def test_player_seasons_are_nba_only_newest_first_with_sorted_teams(session: Session) -> None:
    """The ABA 2004 row and its `ATL` stint belong to the player but are out of v1 scope."""
    assert count_player_seasons(session, "jamesle01") == 3
    assert list_player_seasons(session, "jamesle01", offset=0, limit=100) == [
        PlayerSeasonIdentity(season_year=2005, league="NBA", teams=()),
        PlayerSeasonIdentity(season_year=2004, league="NBA", teams=("CLE", "MIA")),
        PlayerSeasonIdentity(season_year=2003, league="NBA", teams=("CLE",)),
    ]


@pytest.mark.unit
def test_player_seasons_paginate(session: Session) -> None:
    assert [
        season.season_year
        for season in list_player_seasons(session, "jamesle01", offset=1, limit=1)
    ] == [2004]
    assert list_player_seasons(session, "jamesle01", offset=3, limit=2) == []


@pytest.mark.unit
def test_player_seasons_of_players_without_seasons_or_unknown_players_are_empty(
    session: Session,
) -> None:
    for player_id in ("rookiaa01", "unknown01", "JAMESLE01"):
        assert count_player_seasons(session, player_id) == 0, player_id
        assert list_player_seasons(session, player_id, offset=0, limit=50) == [], player_id


@pytest.mark.unit
def test_get_player_season_is_nba_scoped_and_carries_its_teams(session: Session) -> None:
    assert get_player_season(session, "jamesle01", 2004) == PlayerSeasonIdentity(
        season_year=2004, league="NBA", teams=("CLE", "MIA")
    )
    assert get_player_season(session, "jamesle01", 2005) == PlayerSeasonIdentity(
        season_year=2005, league="NBA", teams=()
    )
    assert get_player_season(session, "jamesle01", 1999) is None
    assert get_player_season(session, "smithjo01", 2004) is None
    assert get_player_season(session, "unknown01", 2004) is None


@pytest.mark.unit
def test_teams_load_in_one_query_for_the_whole_page(
    session: Session, statements: StatementLog
) -> None:
    """Three seasons, two statements: the page and its teams. Never one query per season."""
    list_player_seasons(session, "jamesle01", offset=0, limit=100)

    assert len(statements.statements) == 2


@pytest.mark.unit
def test_player_queries_only_read_and_leave_the_session_unchanged(
    session: Session, statements: StatementLog
) -> None:
    count_players(session)
    list_players(session, offset=0, limit=100)
    get_player(session, "jamesle01")
    count_player_seasons(session, "jamesle01")
    list_player_seasons(session, "jamesle01", offset=0, limit=100)
    get_player_season(session, "jamesle01", 2004)

    assert statements.statements
    assert all(
        statement.lstrip().upper().startswith("SELECT") for statement in statements.statements
    ), statements.statements
    assert not session.new
    assert not session.dirty
    assert not session.deleted
