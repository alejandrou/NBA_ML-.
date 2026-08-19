from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.scraping.loaders import TeamSeasonLoadBatch, load_team_season_core
from nba_data.validation.team_season import TeamSeasonDataQualityError

CORE_TABLES = (
    Season.__table__,
    Team.__table__,
    TeamAlias.__table__,
    Player.__table__,
    TeamSeason.__table__,
    PlayerSeason.__table__,
    PlayerTeamSeason.__table__,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        for table in CORE_TABLES:
            table.create(connection)

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as test_session:
        yield test_session

    engine.dispose()


@pytest.mark.unit
def test_loader_rerun_creates_no_duplicate_core_rows(session: Session) -> None:
    batch = _batch(rows=[_row(), _row(source_table="roster"), _aggregate_row()])

    first = load_team_season_core(session, batch)
    second = load_team_season_core(session, batch)

    assert first.input_rows == 3
    assert second.input_rows == 3
    assert _count(session, Season) == 1
    assert _count(session, Team) == 1
    assert _count(session, TeamAlias) == 1
    assert _count(session, TeamSeason) == 1
    assert _count(session, Player) == 2
    assert _count(session, PlayerSeason) == 2
    assert _count(session, PlayerTeamSeason) == 1


@pytest.mark.unit
def test_invalid_batch_performs_no_db_writes(session: Session) -> None:
    batch = _batch(rows=[_row(basketball_reference_player_id=None)])

    with pytest.raises(TeamSeasonDataQualityError):
        load_team_season_core(session, batch)

    assert _all_core_counts(session) == {
        Season: 0,
        Team: 0,
        TeamAlias: 0,
        TeamSeason: 0,
        Player: 0,
        PlayerSeason: 0,
        PlayerTeamSeason: 0,
    }


@pytest.mark.unit
def test_duplicate_natural_keys_fail_before_db_writes(session: Session) -> None:
    row = _row()
    batch = _batch(rows=[row, row.copy()])

    with pytest.raises(TeamSeasonDataQualityError, match="Duplicate normalized"):
        load_team_season_core(session, batch)

    assert _count(session, Season) == 0
    assert _count(session, Player) == 0


@pytest.mark.unit
def test_loader_does_not_commit(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_commit() -> None:
        raise AssertionError("loader must not call session.commit()")

    monkeypatch.setattr(session, "commit", fail_commit)

    load_team_season_core(session, _batch())

    assert _count(session, Season) == 1


@pytest.mark.unit
def test_caller_rollback_removes_inserted_records(session: Session) -> None:
    load_team_season_core(session, _batch())

    assert _count(session, Player) == 1

    session.rollback()

    assert _count(session, Player) == 0
    assert _count(session, Team) == 0
    assert _count(session, Season) == 0


@pytest.mark.unit
def test_existing_meaningful_names_are_not_overwritten_by_fallback_or_empty(
    session: Session,
) -> None:
    team = Team(
        basketball_reference_team_id="BOS",
        current_abbreviation="BOS",
        current_name="Boston Celtics",
    )
    player = Player(
        basketball_reference_player_id="tatumja01",
        full_name="Jayson Tatum",
    )
    session.add_all([team, player])
    session.flush()

    batch = _batch(
        team_name=None,
        rows=[_row(player_name="", basketball_reference_player_id="tatumja01")],
    )

    load_team_season_core(session, batch)

    assert team.current_name == "Boston Celtics"
    assert player.full_name == "Jayson Tatum"


@pytest.mark.unit
def test_real_team_name_upgrades_existing_abbreviation_fallback(session: Session) -> None:
    load_team_season_core(session, _batch(team_name=None))

    team = session.scalar(select(Team).where(Team.basketball_reference_team_id == "BOS"))
    alias = session.scalar(select(TeamAlias).where(TeamAlias.abbreviation == "BOS"))
    assert team is not None
    assert team.current_name == "BOS"
    assert alias is not None
    assert alias.name == "BOS"

    load_team_season_core(session, _batch(team_name="Boston Celtics"))

    assert team.current_name == "Boston Celtics"
    assert alias.name == "Boston Celtics"


@pytest.mark.unit
def test_player_name_is_not_used_as_identity(session: Session) -> None:
    batch = _batch(
        rows=[
            _row(player_name="Same Name", basketball_reference_player_id="sameaa01"),
            _row(player_name="Same Name", basketball_reference_player_id="samebb01"),
        ]
    )

    load_team_season_core(session, batch)

    assert _count(session, Player) == 2


@pytest.mark.unit
def test_tot_aggregate_does_not_create_real_team_rows(session: Session) -> None:
    batch = _batch(rows=[_aggregate_row()])

    load_team_season_core(session, batch)

    assert _count(session, Team) == 1
    assert session.scalar(
        select(func.count()).select_from(Team).where(Team.basketball_reference_team_id == "TOT")
    ) == 0
    assert _count(session, TeamSeason) == 1
    assert _count(session, PlayerSeason) == 1
    assert _count(session, PlayerTeamSeason) == 0


@pytest.mark.unit
def test_roster_values_persist_and_non_roster_rows_do_not_clear_them(session: Session) -> None:
    batch = _batch(rows=[_row(source_table="totals"), _row(source_table="roster")])

    load_team_season_core(session, batch)
    load_team_season_core(session, _batch(rows=[_row(source_table="totals")]))

    player_team_season = session.scalar(select(PlayerTeamSeason))
    assert player_team_season is not None
    assert player_team_season.roster_number == "0"
    assert player_team_season.roster_position == "SF"


def _batch(
    *,
    rows: list[dict[str, object]] | None = None,
    team_name: str | None = "Boston Celtics",
) -> TeamSeasonLoadBatch:
    return TeamSeasonLoadBatch(
        league="NBA",
        season_year=2024,
        team_abbreviation="BOS",
        team_name=team_name,
        rows=rows or [_row()],
    )


def _row(**overrides: object) -> dict[str, object]:
    source_table = str(overrides.pop("source_table", "totals"))
    stat_scope = "team_roster" if source_table == "roster" else "player_team_season"
    values: dict[str, object] = {"games": 74}
    if source_table == "roster":
        values = {"number": 0, "pos": "SF"}

    row: dict[str, object] = {
        "league": "NBA",
        "season_year": 2024,
        "team_abbreviation": "BOS",
        "team_context": "team",
        "source_table": source_table,
        "stat_scope": stat_scope,
        "player_name": "Jayson Tatum",
        "basketball_reference_player_id": "tatumja01",
        "stable_player_key": "tatumja01",
        "identifier_status": "present",
        "values": values,
    }
    row.update(overrides)
    return row


def _aggregate_row(**overrides: object) -> dict[str, object]:
    row = _row(
        team_abbreviation="TOT",
        team_context="aggregate",
        source_table="totals",
        stat_scope="player_season_aggregate",
        player_name="Jaylen Brown",
        basketball_reference_player_id="brownja02",
        stable_player_key="brownja02",
    )
    row.update(overrides)
    return row


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _all_core_counts(session: Session) -> dict[type, int]:
    return {
        Season: _count(session, Season),
        Team: _count(session, Team),
        TeamAlias: _count(session, TeamAlias),
        TeamSeason: _count(session, TeamSeason),
        Player: _count(session, Player),
        PlayerSeason: _count(session, PlayerSeason),
        PlayerTeamSeason: _count(session, PlayerTeamSeason),
    }
