"""`load_team_game_history` reads the history games in one SELECT and writes nothing.

SQLite stands in for PostgreSQL; the PostgreSQL-only regular expression checks
are left out of its tables, and `tests/integration/test_team_game_history_postgres.py`
runs the same query with every constraint in force.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import CheckConstraint, MetaData, create_engine, event
from sqlalchemy.orm import Session

from nba_data.db.models import Game, Season, Team, TeamGameTotals, TeamSeason
from nba_data.ml.team_games import TeamBox, TeamGameRecord, load_team_game_history

TABLES = (Season, Team, TeamSeason, Game, TeamGameTotals)
_LINEAGE = {"source_url": "u", "cache_path": "c", "parser_version": "p"}


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
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for model in TABLES:
            table = model.__table__.to_metadata(metadata)  # type: ignore[attr-defined]
            # SQLite cannot evaluate PostgreSQL's `~` regular expression checks.
            for constraint in list(table.constraints):
                if isinstance(constraint, CheckConstraint) and "~" in str(constraint.sqltext):
                    table.constraints.discard(constraint)
        metadata.create_all(connection)
        with Session(bind=connection) as seed:
            _seed(seed)
            seed.commit()
        event.listen(connection, "before_cursor_execute", statements)
        with Session(bind=connection) as test_session:
            yield test_session
    engine.dispose()


def _seed(session: Session) -> None:
    session.add_all(
        [
            Season(id=1, season_year=2024, league="NBA"),
            Season(id=2, season_year=2025, league="NBA"),
            Season(id=3, season_year=2025, league="ABA"),
            Team(id=1, basketball_reference_team_id="BOS", current_name="Celtics"),
            Team(id=2, basketball_reference_team_id="DEN", current_name="Nuggets"),
            TeamSeason(id=11, team_id=1, season_id=1, team_abbreviation="BOS"),
            TeamSeason(id=12, team_id=2, season_id=1, team_abbreviation="DEN"),
            TeamSeason(id=21, team_id=1, season_id=2, team_abbreviation="BOS"),
            TeamSeason(id=22, team_id=2, season_id=2, team_abbreviation="DEN"),
            TeamSeason(id=31, team_id=1, season_id=3, team_abbreviation="BOS"),
            TeamSeason(id=32, team_id=2, season_id=3, team_abbreviation="DEN"),
        ]
    )
    # Surrogate ids run against date order, so only the declared ordering can
    # put the records right.
    games = [
        (1, "202501020BOS", 2, 21, 22, date(2025, 1, 2), "regular_season", "final", None),
        (2, "202412140DEN", 2, 22, 21, date(2024, 12, 14), "cup_final", "final", True),
        (3, "202401050DEN", 1, 12, 11, date(2024, 1, 5), "regular_season", "final", False),
        (4, "202401050BOS", 1, 11, 12, date(2024, 1, 5), "regular_season", "final", False),
        (5, "202404200BOS", 1, 11, 12, date(2024, 4, 20), "playoffs", "final", False),
        (6, "202404160DEN", 1, 12, 11, date(2024, 4, 16), "play_in", "final", False),
        (7, "202501100BOS", 2, 21, 22, date(2025, 1, 10), None, "scheduled", None),
        (8, "202501120DEN", 2, 22, 21, date(2025, 1, 12), None, "postponed", None),
        (9, "202501030BOS", 3, 31, 32, date(2025, 1, 3), "regular_season", "final", False),
    ]
    for game_id, bref_id, season_id, home, away, day, game_type, status, neutral in games:
        session.add(
            Game(
                id=game_id,
                basketball_reference_game_id=bref_id,
                season_id=season_id,
                home_team_season_id=home,
                away_team_season_id=away,
                game_date=day,
                game_type=game_type,
                status=status,
                neutral_site=neutral,
            )
        )
    session.flush()
    for game_id, team_season_id, is_home, pts, tov in [
        (1, 21, True, 101, 12),
        (1, 22, False, 99, None),
        (2, 22, True, 110, 14),
        (2, 21, False, 108, 15),
        (3, 12, True, 95, 11),
        (3, 11, False, 97, 10),
        (4, 11, True, 120, 9),
        # Game 4's away totals are missing: the record keeps the game, blank.
        (5, 11, True, 100, 9),
        (5, 12, False, 90, 9),
        (6, 12, True, 100, 9),
        (6, 11, False, 90, 9),
        (9, 31, True, 100, 9),
        (9, 32, False, 90, 9),
    ]:
        session.add(
            TeamGameTotals(
                game_id=game_id,
                team_season_id=team_season_id,
                is_home=is_home,
                seconds_played=14400,
                pts=pts,
                fg=40,
                fga=85,
                fg3=12,
                ft=18,
                fta=22,
                orb=10,
                drb=33,
                tov=tov,
                **_LINEAGE,
            )
        )


def _box(code: str, pts: int | None, tov: int | None) -> TeamBox:
    return TeamBox(code, pts, 14400, 40, 85, 12, 18, 22, 10, 33, tov)


def test_history_is_final_nba_regular_season_and_cup_final_games_in_date_order(
    session: Session,
) -> None:
    records = load_team_game_history(session)

    assert records == [
        TeamGameRecord(
            "202401050BOS", 2024, date(2024, 1, 5), "regular_season", "final", False,
            _box("BOS", 120, 9), TeamBox("DEN", *([None] * 10)),
        ),
        TeamGameRecord(
            "202401050DEN", 2024, date(2024, 1, 5), "regular_season", "final", False,
            _box("DEN", 95, 11), _box("BOS", 97, 10),
        ),
        TeamGameRecord(
            "202412140DEN", 2025, date(2024, 12, 14), "cup_final", "final", True,
            _box("DEN", 110, 14), _box("BOS", 108, 15),
        ),
        TeamGameRecord(
            "202501020BOS", 2025, date(2025, 1, 2), "regular_season", "final", None,
            _box("BOS", 101, 12), _box("DEN", 99, None),
        ),
    ]  # fmt: skip


def test_the_read_is_one_select_and_leaves_the_session_clean(
    session: Session, statements: StatementLog
) -> None:
    load_team_game_history(session)

    assert len(statements.statements) == 1
    assert statements.statements[0].lstrip().upper().startswith("SELECT")
    assert not session.new and not session.dirty and not session.deleted


def test_a_dirty_session_is_not_flushed_by_the_read(
    session: Session, statements: StatementLog
) -> None:
    assert session.autoflush
    team = session.get(Team, 1)
    statements.statements.clear()
    assert team is not None
    team.current_name = "Renamed"

    load_team_game_history(session)

    assert len(statements.statements) == 1
    assert statements.statements[0].lstrip().upper().startswith("SELECT")
    assert team in session.dirty


def test_an_empty_database_gives_no_records(session: Session) -> None:
    session.query(TeamGameTotals).delete()
    session.query(Game).delete()

    assert load_team_game_history(session) == []
