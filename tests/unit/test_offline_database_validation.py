from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.validation.offline_database import (
    OfflineDatabaseValidationExpectations,
    validate_offline_database,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
    _create_core_tables(connection)

    session_factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    with session_factory() as test_session:
        yield test_session

    connection.close()
    engine.dispose()


@pytest.mark.unit
def test_validate_offline_database_accepts_clean_phase_4d_shape(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_offline_database(
        session,
        _backfill_report(),
        _expectations(),
    )

    assert report.passed is True
    assert report.table_counts["core.team_seasons"] == 1
    assert report.season_counts == (
        {
            "season_year": 2024,
            "team_seasons": 1,
            "player_seasons": 1,
            "player_team_seasons": 1,
        },
    )
    assert report.to_dict()["issues"] == []


@pytest.mark.unit
def test_validate_offline_database_reports_count_mismatch(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_offline_database(
        session,
        _backfill_report(),
        _expectations(table_counts={"core.players": 2}),
    )

    assert report.passed is False
    assert _issue_codes(report) == {"table_count_mismatch"}


@pytest.mark.unit
def test_validate_offline_database_detects_duplicate_logical_rows(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values (2, 1, 1, 'BOS')"
        )
    )

    report = validate_offline_database(
        session,
        _backfill_report(),
        _expectations(table_counts={"core.team_seasons": 2}),
    )

    assert report.passed is False
    assert {
        "duplicate_team_seasons_by_team",
        "duplicate_team_seasons_by_abbreviation",
    } <= _issue_codes(report)


@pytest.mark.unit
def test_validate_offline_database_detects_orphans(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.player_team_seasons "
            "(id, player_season_id, team_season_id) values (2, 999, 1)"
        )
    )

    report = validate_offline_database(
        session,
        _backfill_report(),
        _expectations(table_counts={"core.player_team_seasons": 2}),
    )

    assert report.passed is False
    assert "orphan_player_team_seasons_player_season" in _issue_codes(report)


@pytest.mark.unit
def test_validate_offline_database_detects_team_seasons_without_players(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text("insert into core.teams (id, basketball_reference_team_id, current_name) "
             "values (2, 'DEN', 'Denver Nuggets')")
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values (2, 2, 1, 'DEN')"
        )
    )

    report = validate_offline_database(
        session,
        _backfill_report(),
        _expectations(table_counts={"core.teams": 2, "core.team_seasons": 2}),
    )

    assert report.passed is False
    assert "team_seasons_without_players" in _issue_codes(report)


@pytest.mark.unit
def test_validate_offline_database_detects_tot_as_real_team(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text("insert into core.teams (id, basketball_reference_team_id, current_name) "
             "values (2, 'TOT', 'Total')")
    )
    session.execute(
        text(
            "insert into core.team_aliases "
            "(id, team_id, abbreviation, name, from_season_year, to_season_year) "
            "values (2, 2, 'TOT', 'Total', 2024, 2024)"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values (2, 2, 1, 'TOT')"
        )
    )

    report = validate_offline_database(
        session,
        _backfill_report(),
        _expectations(
            table_counts={
                "core.teams": 2,
                "core.team_aliases": 2,
                "core.team_seasons": 2,
            }
        ),
    )

    assert report.passed is False
    assert {
        "teams_tot_rows",
        "team_aliases_tot_rows",
        "team_seasons_tot_rows",
    } <= _issue_codes(report)


@pytest.mark.unit
def test_validate_offline_database_checks_backfill_failures_and_quarantine(
    session: Session,
) -> None:
    _insert_clean_dataset(session)

    report = validate_offline_database(
        session,
        _backfill_report(loaded_rows=0, failed_entries=1, quarantined_entries=1),
        _expectations(),
    )

    assert report.passed is False
    assert "backfill_report_mismatch" in _issue_codes(report)


@pytest.mark.unit
def test_cli_validate_offline_database_prints_json_and_exits_one_on_issues(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    backfill_report = tmp_path / "offline-backfill.json"
    backfill_report.write_text(json.dumps({"selected_inventory_entries": 1}), encoding="utf-8")

    class FakeValidationReport:
        passed = False

        def to_dict(self) -> dict[str, object]:
            return {"passed": False, "issues": [{"code": "synthetic"}]}

    class FakeEngine:
        def dispose(self) -> None:
            events.append("engine_dispose")

    class FakeSession:
        def __enter__(self) -> FakeSession:
            events.append("session_enter")
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            events.append("session_exit")

    fake_engine = FakeEngine()
    fake_session = FakeSession()

    def fake_engine_factory(settings: object) -> FakeEngine:
        events.append("engine_create")
        return fake_engine

    def fake_session_factory(engine: object) -> object:
        assert engine is fake_engine
        events.append("session_factory_create")
        return lambda: fake_session

    def fake_validate(session: object, backfill_data: object) -> FakeValidationReport:
        assert session is fake_session
        assert backfill_data == {"selected_inventory_entries": 1}
        events.append("validate")
        return FakeValidationReport()

    monkeypatch.setattr("nba_data.cli.main.create_db_engine", fake_engine_factory)
    monkeypatch.setattr("nba_data.cli.main.create_session_factory", fake_session_factory)
    monkeypatch.setattr("nba_data.cli.main.run_offline_database_validation", fake_validate)

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "offline-database",
            "--backfill-report",
            str(backfill_report),
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {"passed": False, "issues": [{"code": "synthetic"}]}
    assert events == [
        "engine_create",
        "session_factory_create",
        "session_enter",
        "validate",
        "session_exit",
        "engine_dispose",
    ]


def _create_core_tables(connection: Connection) -> None:
    connection.exec_driver_sql(
        """
        create table core.seasons (
            id integer primary key,
            season_year integer not null,
            league varchar(20) not null,
            label varchar(20)
        )
        """
    )
    connection.exec_driver_sql(
        """
        create table core.teams (
            id integer primary key,
            basketball_reference_team_id varchar(10),
            current_abbreviation varchar(10),
            current_name varchar(200) not null,
            franchise_id varchar(100)
        )
        """
    )
    connection.exec_driver_sql(
        """
        create table core.team_aliases (
            id integer primary key,
            team_id integer not null,
            abbreviation varchar(10) not null,
            name varchar(200) not null,
            from_season_year integer,
            to_season_year integer
        )
        """
    )
    connection.exec_driver_sql(
        """
        create table core.players (
            id integer primary key,
            basketball_reference_player_id varchar(32),
            full_name varchar(200) not null,
            slug varchar(200)
        )
        """
    )
    connection.exec_driver_sql(
        """
        create table core.team_seasons (
            id integer primary key,
            team_id integer not null,
            season_id integer not null,
            team_abbreviation varchar(10) not null
        )
        """
    )
    connection.exec_driver_sql(
        """
        create table core.player_seasons (
            id integer primary key,
            player_id integer not null,
            season_id integer not null
        )
        """
    )
    connection.exec_driver_sql(
        """
        create table core.player_team_seasons (
            id integer primary key,
            player_season_id integer not null,
            team_season_id integer not null,
            roster_number varchar(20),
            roster_position varchar(50)
        )
        """
    )


def _insert_clean_dataset(session: Session) -> None:
    session.execute(
        text("insert into core.seasons (id, season_year, league, label) "
             "values (1, 2024, 'NBA', '2024')")
    )
    session.execute(
        text(
            "insert into core.teams "
            "(id, basketball_reference_team_id, current_abbreviation, current_name) "
            "values (1, 'BOS', 'BOS', 'Boston Celtics')"
        )
    )
    session.execute(
        text(
            "insert into core.team_aliases "
            "(id, team_id, abbreviation, name, from_season_year, to_season_year) "
            "values (1, 1, 'BOS', 'Boston Celtics', 2024, 2024)"
        )
    )
    session.execute(
        text("insert into core.players (id, basketball_reference_player_id, full_name) "
             "values (1, 'tatumja01', 'Jayson Tatum')")
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values (1, 1, 1, 'BOS')"
        )
    )
    session.execute(
        text("insert into core.player_seasons (id, player_id, season_id) values (1, 1, 1)")
    )
    session.execute(
        text(
            "insert into core.player_team_seasons "
            "(id, player_season_id, team_season_id) values (1, 1, 1)"
        )
    )


def _expectations(
    *,
    table_counts: dict[str, int] | None = None,
) -> OfflineDatabaseValidationExpectations:
    counts = {
        "core.seasons": 1,
        "core.teams": 1,
        "core.team_aliases": 1,
        "core.team_seasons": 1,
        "core.players": 1,
        "core.player_seasons": 1,
        "core.player_team_seasons": 1,
    }
    counts.update(table_counts or {})
    return OfflineDatabaseValidationExpectations(
        table_counts=counts,
        expected_start_year=2024,
        expected_end_year=2024,
        min_team_seasons_per_season=1,
        min_player_seasons_per_season=1,
        min_player_team_seasons_per_season=1,
        expected_backfill_selected_inventory_entries=1,
        expected_backfill_loaded_entries=1,
        expected_backfill_loaded_rows=1,
    )


def _backfill_report(
    *,
    loaded_rows: int = 1,
    failed_entries: int = 0,
    quarantined_entries: int = 0,
    quarantined_rows: int = 0,
) -> dict[str, object]:
    return {
        "selected_inventory_entries": 1,
        "skipped_inventory_entries": 0,
        "processing_report": {
            "validated_entries": 1,
            "failed_entries": 0,
            "validated_row_count": loaded_rows,
        },
        "load_report": {
            "loaded_entries": 1,
            "loaded_rows": loaded_rows,
            "failed_entries": failed_entries,
            "skipped_entries": 0,
        },
        "audit_report": {
            "quarantined_entries": quarantined_entries,
            "quarantined_rows": quarantined_rows,
        },
    }


def _issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}
