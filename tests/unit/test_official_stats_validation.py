from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.validation.official_stats import STATS_TABLE_SPECS, validate_official_stats


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
    connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
    _create_core_tables(connection)
    _create_stats_tables(connection)

    session_factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    with session_factory() as test_session:
        yield test_session

    connection.close()
    engine.dispose()


@pytest.mark.unit
def test_validate_official_stats_accepts_clean_phase_4e_shape(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_official_stats(session, _stats_backfill_report())

    assert report.passed is True
    assert len(report.table_counts) == 17
    assert report.table_counts["stats.player_team_season_roster"] == 1
    assert report.backfill_summary["stats_loaded_rows"] == 17
    assert report.to_dict()["issues"] == []


@pytest.mark.unit
def test_validate_official_stats_reports_all_table_counts(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_official_stats(session)

    assert set(report.table_counts) == {f"stats.{spec.table_name}" for spec in STATS_TABLE_SPECS}
    assert all(count == 1 for count in report.table_counts.values())


@pytest.mark.unit
def test_validate_official_stats_detects_duplicate_rows(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into stats.player_team_season_totals "
            "(id, player_team_season_id, source_url, cache_path, parser_version, age, g, gs, mp, fg_pct, pts) "
            "values (2, 1, 'dup', 'dup', 'v1', 26, 82, 80, 2800, 0.5, 2000)"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert _issue_codes(report) == {"duplicate_logical_rows"}


@pytest.mark.unit
def test_validate_official_stats_detects_orphan_and_invalid_grains(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.player_team_seasons "
            "(id, player_season_id, team_season_id) values (3, 1, 999)"
        )
    )
    session.execute(
        text(
            "insert into stats.player_team_season_per_game "
            "(id, player_team_season_id, source_url, cache_path, parser_version, age, g, gs, mp_per_game, fg_pct) "
            "values (2, 3, 'bad-chain', 'bad-chain', 'v1', 26, 82, 80, 34.0, 0.5)"
        )
    )
    session.execute(
        text(
            "insert into stats.player_season_totals "
            "(id, player_season_id, source_url, cache_path, parser_version, age, g, gs, mp, fg_pct, pts) "
            "values (2, 999, 'orphan', 'orphan', 'v1', 26, 82, 80, 2800, 0.5, 2000)"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert {"invalid_core_grain_chain", "orphan_fk_grain"} <= _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_team_stint_tot_misuse(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.teams "
            "(id, basketball_reference_team_id, current_abbreviation, current_name) "
            "values (3, 'TOT', 'TOT', 'Total')"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values (3, 3, 1, 'TOT')"
        )
    )
    session.execute(
        text(
            "insert into core.player_team_seasons "
            "(id, player_season_id, team_season_id) values (3, 1, 3)"
        )
    )
    session.execute(
        text(
            "insert into stats.player_team_season_advanced "
            "(id, player_team_season_id, source_url, cache_path, parser_version, age, g, gs, mp, per, ts_pct) "
            "values (2, 3, 'tot', 'tot', 'v1', 26, 82, 80, 2800, 20, 0.6)"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert "tot_in_team_stint_table" in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_single_stint_aggregate_rows(session: Session) -> None:
    _insert_clean_dataset(session, multi_stint=False)

    report = validate_official_stats(session)

    assert report.passed is False
    assert "aggregate_row_not_multi_stint" in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_impossible_numeric_values_and_null_rows(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_team_season_totals set age = 10, g = 5, gs = 6, fg_pct = 1.5 where id = 1"
        )
    )
    session.execute(
        text(
            "insert into stats.player_season_shooting "
            "(id, player_season_id, source_url, cache_path, parser_version) "
            "values (2, 1, 'nulls', 'nulls', 'v1')"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert {"all_stat_columns_null", "impossible_numeric_values"} <= _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_generated_metric_schema_names(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(text("alter table stats.player_season_advanced add column ovr_score numeric"))

    report = validate_official_stats(session)

    assert report.passed is False
    assert "generated_metric_schema_name" in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_checks_stats_backfill_report(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_official_stats(
        session,
        _stats_backfill_report(
            stats_loaded_rows=16,
            processing_failed_sources=1,
            stats_failed_rows=2,
            stats_quarantined_rows=3,
        ),
    )

    assert report.passed is False
    assert {"backfill_failures_present", "backfill_row_mismatch"} <= _issue_codes(report)


@pytest.mark.unit
def test_cli_validate_official_stats_prints_json_and_exits_one_on_issues(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    backfill_report = tmp_path / "stats-backfill.json"
    backfill_report.write_text(json.dumps({"stats_loaded_rows": 17}), encoding="utf-8")

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
        assert backfill_data == {"stats_loaded_rows": 17}
        events.append("validate")
        return FakeValidationReport()

    monkeypatch.setattr("nba_data.cli.main.create_db_engine", fake_engine_factory)
    monkeypatch.setattr("nba_data.cli.main.create_session_factory", fake_session_factory)
    monkeypatch.setattr("nba_data.cli.main.run_official_stats_validation", fake_validate)

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "official-stats",
            "--stats-backfill-report",
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
            current_name varchar(200) not null
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
        create table core.players (
            id integer primary key,
            basketball_reference_player_id varchar(32),
            full_name varchar(200) not null
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
            team_season_id integer not null
        )
        """
    )


def _create_stats_tables(connection: Connection) -> None:
    for spec in STATS_TABLE_SPECS:
        extra_columns = _stats_extra_columns(spec.table_name)
        common_columns = [
            "id integer primary key",
            f"{spec.grain_column} integer not null",
            "source_url text not null",
            "cache_path text not null",
            "parser_version varchar(50) not null",
            "created_at text",
            "updated_at text",
        ]
        column_sql = ", ".join(common_columns + extra_columns)
        connection.exec_driver_sql(f"create table stats.{spec.table_name} ({column_sql})")


def _stats_extra_columns(table_name: str) -> list[str]:
    if table_name == "player_team_season_roster":
        return [
            "jersey_number text",
            "player_name text",
            "position text",
            "weight integer",
        ]
    if table_name.endswith("_totals"):
        return ["age integer", "g integer", "gs integer", "mp integer", "fg_pct numeric", "pts integer"]
    if table_name.endswith("_per_game"):
        return ["age integer", "g integer", "gs integer", "mp_per_game numeric", "fg_pct numeric"]
    if table_name.endswith("_per_minute"):
        return ["age integer", "g integer", "gs integer", "mp integer", "fg_pct numeric"]
    if table_name.endswith("_per_poss"):
        return ["age integer", "g integer", "gs integer", "mp integer", "fg_pct numeric", "ortg numeric", "drtg numeric"]
    if table_name.endswith("_advanced"):
        return ["age integer", "g integer", "gs integer", "mp integer", "per numeric", "ts_pct numeric"]
    if table_name.endswith("_adj_shooting"):
        return [
            "age integer",
            "g integer",
            "gs integer",
            "mp integer",
            "fg_pct numeric",
            "adj_fg_pct numeric",
            "ts_pct numeric",
            "adj_ts_pct numeric",
        ]
    if table_name.endswith("_shooting"):
        return ["age integer", "g integer", "gs integer", "mp integer", "fg_pct numeric", "avg_dist numeric"]
    if table_name.endswith("_pbp"):
        return ["age integer", "g integer", "gs integer", "mp integer", "pct_pg numeric", "net_plus_minus numeric"]
    raise AssertionError(f"Unhandled stats table {table_name}")


def _insert_clean_dataset(session: Session, *, multi_stint: bool = True) -> None:
    session.execute(
        text("insert into core.seasons (id, season_year, league, label) values (1, 2024, 'NBA', '2024')")
    )
    session.execute(
        text(
            "insert into core.teams "
            "(id, basketball_reference_team_id, current_abbreviation, current_name) "
            "values (1, 'BOS', 'BOS', 'Boston Celtics'), (2, 'LAL', 'LAL', 'Los Angeles Lakers')"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values "
            "(1, 1, 1, 'BOS'), (2, 2, 1, 'LAL')"
        )
    )
    session.execute(
        text(
            "insert into core.players (id, basketball_reference_player_id, full_name) "
            "values (1, 'tatumja01', 'Jayson Tatum')"
        )
    )
    session.execute(text("insert into core.player_seasons (id, player_id, season_id) values (1, 1, 1)"))
    session.execute(
        text(
            "insert into core.player_team_seasons (id, player_season_id, team_season_id) values "
            "(1, 1, 1)"
        )
    )
    if multi_stint:
        session.execute(
            text("insert into core.player_team_seasons (id, player_season_id, team_season_id) values (2, 1, 2)")
        )

    for spec in STATS_TABLE_SPECS:
        params = _stats_row_params(spec.table_name)
        params["id"] = 1
        params[spec.grain_column] = 1
        columns = ", ".join(params)
        values = ", ".join(f":{column}" for column in params)
        session.execute(
            text(f"insert into stats.{spec.table_name} ({columns}) values ({values})"),
            params,
        )


def _stats_row_params(table_name: str) -> dict[str, object]:
    base = {
        "source_url": "https://example.test/team-season",
        "cache_path": "cache/example.html.gz",
        "parser_version": "v1",
    }
    if table_name == "player_team_season_roster":
        return {
            **base,
            "jersey_number": "0",
            "player_name": "Jayson Tatum",
            "position": "SF",
            "weight": 210,
        }
    if table_name.endswith("_totals"):
        return {**base, "age": 26, "g": 82, "gs": 80, "mp": 2800, "fg_pct": 0.5, "pts": 2000}
    if table_name.endswith("_per_game"):
        return {**base, "age": 26, "g": 82, "gs": 80, "mp_per_game": 34.1, "fg_pct": 0.5}
    if table_name.endswith("_per_minute"):
        return {**base, "age": 26, "g": 82, "gs": 80, "mp": 2800, "fg_pct": 0.5}
    if table_name.endswith("_per_poss"):
        return {**base, "age": 26, "g": 82, "gs": 80, "mp": 2800, "fg_pct": 0.5, "ortg": 118, "drtg": 109}
    if table_name.endswith("_advanced"):
        return {**base, "age": 26, "g": 82, "gs": 80, "mp": 2800, "per": 21.5, "ts_pct": 0.61}
    if table_name.endswith("_adj_shooting"):
        return {
            **base,
            "age": 26,
            "g": 82,
            "gs": 80,
            "mp": 2800,
            "fg_pct": 0.5,
            "adj_fg_pct": 1.05,
            "ts_pct": 0.61,
            "adj_ts_pct": 1.02,
        }
    if table_name.endswith("_shooting"):
        return {**base, "age": 26, "g": 82, "gs": 80, "mp": 2800, "fg_pct": 0.5, "avg_dist": 14.2}
    if table_name.endswith("_pbp"):
        return {**base, "age": 26, "g": 82, "gs": 80, "mp": 2800, "pct_pg": 0.1, "net_plus_minus": 8.5}
    raise AssertionError(f"Unhandled stats row {table_name}")


def _stats_backfill_report(
    *,
    stats_loaded_rows: int = 17,
    processing_failed_sources: int = 0,
    stats_failed_rows: int = 0,
    stats_quarantined_rows: int = 0,
) -> dict[str, object]:
    return {
        "selected_sources": 1,
        "processed_sources": 1,
        "processing_failed_sources": processing_failed_sources,
        "stats_loaded_rows": stats_loaded_rows,
        "stats_skipped_rows": 0,
        "stats_failed_rows": stats_failed_rows,
        "stats_quarantined_rows": stats_quarantined_rows,
    }


def _issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}
