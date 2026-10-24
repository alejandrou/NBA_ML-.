from collections.abc import Iterator
from decimal import Decimal
from typing import Any

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
from nba_data.db.models.stats import (
    PlayerSeasonTotals,
    PlayerTeamSeasonAdvanced,
    PlayerTeamSeasonTotals,
)
from nba_data.db.repositories.queries.player_stats import (
    AGGREGATE_TABLES,
    STINT_TABLES,
    UNPUBLISHED_COLUMNS,
    count_stint_stats,
    get_aggregate_stats,
    get_player_season_id,
    list_stint_stats,
)
from nba_data.domain.stat_dimensions import SeasonType, StatFamily

CORE_TABLES = (Season, Team, Player, TeamSeason, PlayerSeason, PlayerTeamSeason)
STAT_TABLES = tuple(
    table
    for tables in (AGGREGATE_TABLES, STINT_TABLES)
    for by_family in tables.values()
    for table in by_family.values()
)
LINEAGE: dict[str, Any] = {
    "source_url": "https://www.basketball-reference.com/players/j/jamesle01.html",
    "cache_path": "data/raw/players/j/jamesle01.html",
    "parser_version": "player-page-v4",
}
PRIVATE_KEYS = {
    "id",
    "player_season_id",
    "player_team_season_id",
    "player_name_display",
    "source_url",
    "cache_path",
    "parser_version",
    "created_at",
    "updated_at",
}


class StatementLog:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def __call__(self, conn: object, cursor: object, statement: str, *args: object) -> None:
        self.statements.append(statement)


@pytest.fixture
def statements() -> StatementLog:
    return StatementLog()


@pytest.fixture
def session(statements: StatementLog) -> Iterator[Session]:
    """`jamesle01`'s 2004 stints are inserted `MIA` before `CLE`, so stat row ids
    would order them the wrong way round; `onlyaba01` has only an ABA season.
    """
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for model in (*CORE_TABLES, *STAT_TABLES):
            model.__table__.create(connection)  # type: ignore[attr-defined]
        with Session(bind=connection) as session:
            session.add_all(
                [
                    Season(id=1, season_year=2003, league="NBA", label="2003"),
                    Season(id=2, season_year=2004, league="NBA", label="2004"),
                    Season(id=4, season_year=1975, league="ABA", label="1975"),
                    Team(id=1, basketball_reference_team_id="CLE", current_name="Cavaliers"),
                    Team(id=2, basketball_reference_team_id="MIA", current_name="Heat"),
                    Team(id=3, basketball_reference_team_id="KEN", current_name="Colonels"),
                    TeamSeason(id=1, team_id=1, season_id=1, team_abbreviation="CLE"),
                    TeamSeason(id=2, team_id=1, season_id=2, team_abbreviation="CLE"),
                    TeamSeason(id=3, team_id=2, season_id=2, team_abbreviation="MIA"),
                    TeamSeason(id=4, team_id=3, season_id=4, team_abbreviation="KEN"),
                    Player(
                        id=5, basketball_reference_player_id="jamesle01", full_name="LeBron James"
                    ),
                    Player(id=6, basketball_reference_player_id="onlyaba01", full_name="Only Aba"),
                    PlayerSeason(id=10, player_id=5, season_id=1),
                    PlayerSeason(id=11, player_id=5, season_id=2),
                    PlayerSeason(id=13, player_id=6, season_id=4),
                    PlayerTeamSeason(id=1, player_season_id=10, team_season_id=1),
                    PlayerTeamSeason(id=2, player_season_id=11, team_season_id=3),
                    PlayerTeamSeason(id=3, player_season_id=11, team_season_id=2),
                    PlayerTeamSeason(id=4, player_season_id=13, team_season_id=4),
                    PlayerSeasonTotals(
                        id=1,
                        player_season_id=11,
                        source_team_code="2TM",
                        player_name_display="LeBron James",
                        g=80,
                        pts=2175,
                        fg_pct=Decimal("0.4660"),
                        **LINEAGE,
                    ),
                    PlayerSeasonTotals(id=2, player_season_id=13, g=1, **LINEAGE),
                    PlayerTeamSeasonTotals(id=1, player_team_season_id=2, g=30, **LINEAGE),
                    PlayerTeamSeasonTotals(id=2, player_team_season_id=3, g=50, **LINEAGE),
                ]
            )
            session.commit()
            session.expunge_all()
            event.listen(connection, "before_cursor_execute", statements)
            yield session
    engine.dispose()


@pytest.mark.unit
def test_the_table_maps_name_every_family_of_both_season_types_at_its_grain() -> None:
    prefixes = {
        SeasonType.REGULAR: ("player_season", "player_team_season"),
        SeasonType.POSTSEASON: ("player_postseason", "player_team_postseason"),
    }
    for season_type, (aggregate_prefix, stint_prefix) in prefixes.items():
        for family in StatFamily:
            aggregate = AGGREGATE_TABLES[season_type][family].__table__
            stint = STINT_TABLES[season_type][family].__table__
            assert aggregate.fullname == f"stats.{aggregate_prefix}_{family.value}"
            assert stint.fullname == f"stats.{stint_prefix}_{family.value}"
            assert "player_season_id" in aggregate.columns
            assert "player_team_season_id" in stint.columns
    assert len(set(STAT_TABLES)) == 32


@pytest.mark.unit
def test_the_unpublished_columns_are_the_keys_lineage_and_display_name() -> None:
    assert UNPUBLISHED_COLUMNS == PRIVATE_KEYS


@pytest.mark.unit
def test_get_player_season_id_resolves_nba_seasons_by_public_year(session: Session) -> None:
    assert get_player_season_id(session, "jamesle01", 2004) == 11
    assert get_player_season_id(session, "jamesle01", 2003) == 10
    assert get_player_season_id(session, "jamesle01", 1999) is None
    assert get_player_season_id(session, "JAMESLE01", 2004) is None
    assert get_player_season_id(session, "onlyaba01", 1975) is None


@pytest.mark.unit
def test_get_aggregate_stats_returns_only_the_published_columns(session: Session) -> None:
    row = get_aggregate_stats(session, PlayerSeasonTotals, 11)

    assert row is not None
    expected = {column.name for column in PlayerSeasonTotals.__table__.columns} - PRIVATE_KEYS
    assert set(row) == expected
    assert row["source_team_code"] == "2TM"
    assert row["fg_pct"] == Decimal("0.4660")
    assert row["pts"] == 2175
    assert row["fg3"] is None


@pytest.mark.unit
def test_get_aggregate_stats_is_none_without_a_stored_row(session: Session) -> None:
    assert get_aggregate_stats(session, PlayerSeasonTotals, 10) is None


@pytest.mark.unit
def test_list_stint_stats_orders_by_team_code_and_paginates(session: Session) -> None:
    rows = list_stint_stats(session, PlayerTeamSeasonTotals, 11, offset=0, limit=100)

    assert [(row["basketball_reference_team_id"], row["g"]) for row in rows] == [
        ("CLE", 50),
        ("MIA", 30),
    ]
    expected = {column.name for column in PlayerTeamSeasonTotals.__table__.columns} - PRIVATE_KEYS
    assert set(rows[0]) == expected | {"basketball_reference_team_id"}
    assert count_stint_stats(session, PlayerTeamSeasonTotals, 11) == 2

    pages = [
        list_stint_stats(session, PlayerTeamSeasonTotals, 11, offset=offset, limit=1)
        for offset in (0, 1, 2)
    ]
    assert [[row["basketball_reference_team_id"] for row in page] for page in pages] == [
        ["CLE"],
        ["MIA"],
        [],
    ]


@pytest.mark.unit
def test_a_stint_without_a_stat_row_is_not_listed(session: Session) -> None:
    """Membership exists for `CLE` 2003, but the totals table holds no row for it."""
    assert list_stint_stats(session, PlayerTeamSeasonTotals, 10, offset=0, limit=100) == []
    assert count_stint_stats(session, PlayerTeamSeasonTotals, 10) == 0
    assert list_stint_stats(session, PlayerTeamSeasonAdvanced, 11, offset=0, limit=100) == []


@pytest.mark.unit
def test_every_mapped_table_is_readable(session: Session) -> None:
    for season_type in SeasonType:
        for family in StatFamily:
            get_aggregate_stats(session, AGGREGATE_TABLES[season_type][family], 11)
            stint = STINT_TABLES[season_type][family]
            list_stint_stats(session, stint, 11, offset=0, limit=1)
            count_stint_stats(session, stint, 11)


@pytest.mark.unit
def test_stat_queries_only_read(session: Session, statements: StatementLog) -> None:
    get_player_season_id(session, "jamesle01", 2004)
    get_aggregate_stats(session, PlayerSeasonTotals, 11)
    list_stint_stats(session, PlayerTeamSeasonTotals, 11, offset=0, limit=10)
    count_stint_stats(session, PlayerTeamSeasonTotals, 11)

    assert statements.statements
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in statements.statements)
    assert not session.new
    assert not session.dirty
    assert not session.deleted
