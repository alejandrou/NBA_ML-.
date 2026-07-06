from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.validation.official_stats import STATS_TABLE_SPECS, validate_official_stats


@pytest.fixture
def session() -> Iterator[Session]:
    with _session_with_schema() as test_session:
        yield test_session


@pytest.mark.unit
def test_validate_official_stats_accepts_clean_final_phase_4e_shape(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_official_stats(session, _stats_backfill_report(stats_loaded_rows=_expected_loaded_rows()))

    assert report.passed is True
    assert len(report.table_counts) == len(STATS_TABLE_SPECS)
    assert report.table_counts["stats.player_team_season_roster"] == 3
    assert report.table_counts["stats.player_season_totals"] == 2
    assert report.table_counts["stats.player_postseason_totals"] == 2
    assert report.validation_summary["synthetic_code_violations"] == 0
    assert report.validation_summary["numeric_range_violations"] == 0
    assert report.backfill_summary["stats_loaded_rows"] == _expected_loaded_rows()
    assert report.to_dict()["issues"] == []


@pytest.mark.unit
def test_validate_official_stats_reports_all_table_counts(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_official_stats(session)

    assert set(report.table_counts) == {f"stats.{spec.table_name}" for spec in STATS_TABLE_SPECS}
    assert sum(report.table_counts.values()) == _expected_loaded_rows()


@pytest.mark.unit
def test_validate_official_stats_detects_missing_tables_and_required_columns() -> None:
    with _session_with_schema(omit_source_team_code_tables={"player_postseason_totals"}) as test_session:
        _insert_clean_dataset(test_session, omit_source_team_code_tables={"player_postseason_totals"})
        test_session.execute(text("drop table stats.player_team_postseason_pbp"))

        report = validate_official_stats(test_session)

    assert report.passed is False
    assert {"missing_stats_table", "missing_required_column"} <= _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_orphan_and_invalid_grains(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.player_team_seasons "
            "(id, player_season_id, team_season_id) values (99, 2, 999)"
        )
    )
    session.execute(
        text(
            "insert into stats.player_team_postseason_per_game "
            "(id, player_team_season_id, source_url, cache_path, parser_version, age, g, gs, mp_per_game, fg_pct) "
            "values (99, 99, 'https://example.test/players/h/hardenja01.html#playoffs', "
            "'cache/player_postseason.html.gz', 'player-page-postseason-parser-v1', 31, 12, 12, 39.4, 0.50)"
        )
    )
    session.execute(
        text(
            "insert into stats.player_postseason_totals "
            "(id, player_season_id, source_team_code, source_url, cache_path, parser_version, age, g, gs, mp, fg_pct, pts) "
            "values (99, 999, 'BRK', 'https://example.test/players/h/hardenja01.html#playoffs', "
            "'cache/player_postseason.html.gz', 'player-page-postseason-parser-v1', 31, 12, 12, 420, 0.50, 320)"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert {"invalid_core_grain_chain", "orphan_fk_grain"} <= _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_synthetic_team_code_misuse(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.teams "
            "(id, basketball_reference_team_id, current_abbreviation, current_name) "
            "values (9, '2TM', '2TM', 'Synthetic Team')"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values (9, 9, 1, '2TM')"
        )
    )
    session.execute(
        text(
            "insert into core.player_team_seasons "
            "(id, player_season_id, team_season_id) values (9, 2, 9)"
        )
    )
    session.execute(
        text(
            "insert into stats.player_team_postseason_totals "
            "(id, player_team_season_id, source_url, cache_path, parser_version, age, g, gs, mp, fg_pct, pts) "
            "values (99, 9, 'https://example.test/players/h/hardenja01.html#playoffs', "
            "'cache/player_postseason.html.gz', 'player-page-postseason-parser-v1', 31, 12, 12, 420, 0.50, 320)"
        )
    )
    session.execute(text("update stats.player_season_totals set source_team_code = 'TOT' where player_season_id = 2"))
    session.execute(text("update stats.player_postseason_totals set source_team_code = 'XYZ' where player_season_id = 1"))

    report = validate_official_stats(session)

    assert report.passed is False
    assert {
        "synthetic_code_in_core_teams",
        "synthetic_code_in_core_team_seasons",
        "synthetic_code_in_core_player_team_seasons",
        "synthetic_code_in_team_stint_stats",
        "invalid_aggregate_source_team_code",
    } <= _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_accepts_basketball_reference_numeric_scales(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_season_advanced "
            "set orb_pct = 100.0, usg_pct = 72.5 where player_season_id = 2"
        )
    )
    session.execute(
        text(
            "update stats.player_team_season_pbp "
            "set pct_pg = 100.0 where player_team_season_id = 1"
        )
    )
    session.execute(
        text(
            "update stats.player_postseason_adj_shooting "
            "set adj_fg_pct = 228.0, adj_ts_pct = 270.0 where player_season_id = 2"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is True
    assert "impossible_numeric_values" not in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_invalid_numeric_ranges(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(text("update stats.player_team_season_totals set fg_pct = 1.1 where player_team_season_id = 1"))
    session.execute(text("update stats.player_season_advanced set usg_pct = 101.0 where player_season_id = 2"))
    session.execute(text("update stats.player_team_postseason_pbp set pct_pg = 101.0 where player_team_season_id = 3"))
    session.execute(text("update stats.player_postseason_adj_shooting set adj_ts_pct = 301.0 where player_season_id = 2"))

    report = validate_official_stats(session)

    assert report.passed is False
    assert "impossible_numeric_values" in _issue_codes(report)
    assert report.validation_summary["numeric_range_violations"] >= 4


@pytest.mark.unit
def test_validate_official_stats_detects_regular_postseason_separation_issues(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_season_totals "
            "set parser_version = 'player-page-postseason-parser-v1' where player_season_id = 2"
        )
    )
    session.execute(
        text(
            "update stats.player_postseason_totals "
            "set parser_version = 'player-page-parser-v1' where player_season_id = 1"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert "regular_postseason_separation_violation" in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_duplicate_rows(session: Session) -> None:
    with _session_with_schema(no_unique_grain_tables={"player_team_season_totals"}) as test_session:
        _insert_clean_dataset(test_session)
        test_session.execute(
            text(
                "insert into stats.player_team_season_totals "
                "(id, player_team_season_id, source_url, cache_path, parser_version, age, g, gs, mp, fg_pct, pts) "
                "values (99, 1, 'dup', 'dup', 'stats-parser-v1', 27, 82, 82, 2900, 0.51, 2100)"
            )
        )

        report = validate_official_stats(test_session)

    assert report.passed is False
    assert "duplicate_logical_rows" in _issue_codes(report)


@pytest.mark.unit
def test_cli_validate_official_stats_prints_json_and_exits_one_on_issues(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    backfill_report = tmp_path / "stats-backfill.json"
    backfill_report.write_text(json.dumps({"stats_loaded_rows": 75}), encoding="utf-8")

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
        assert backfill_data == {"stats_loaded_rows": 75}
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


@contextmanager
def _session_with_schema(
    *,
    omit_source_team_code_tables: set[str] | None = None,
    no_unique_grain_tables: set[str] | None = None,
) -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
    connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
    _create_core_tables(connection)
    _create_stats_tables(
        connection,
        omit_source_team_code_tables=omit_source_team_code_tables or set(),
        no_unique_grain_tables=no_unique_grain_tables or set(),
    )

    session_factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    try:
        with session_factory() as test_session:
            yield test_session
    finally:
        connection.close()
        engine.dispose()


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
        create table core.team_aliases (
            id integer primary key,
            team_id integer not null,
            abbreviation varchar(10) not null
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


def _create_stats_tables(
    connection: Connection,
    *,
    omit_source_team_code_tables: set[str],
    no_unique_grain_tables: set[str],
) -> None:
    for spec in STATS_TABLE_SPECS:
        extra_columns = _stats_extra_columns(spec.table_name)
        common_columns = [
            "id integer primary key",
            f"{spec.grain_column} integer not null",
        ]
        if spec.family == "aggregate" and spec.table_name not in omit_source_team_code_tables:
            common_columns.append("source_team_code varchar(10)")
        common_columns.extend(
            [
                "source_url text not null",
                "cache_path text not null",
                "parser_version varchar(50) not null",
                "created_at text",
                "updated_at text",
            ]
        )
        trailing_constraints: list[str] = []
        if spec.table_name not in no_unique_grain_tables:
            trailing_constraints.append(f"unique ({spec.grain_column})")
        column_sql = ", ".join(common_columns + extra_columns + trailing_constraints)
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
        return [
            "age integer",
            "g integer",
            "gs integer",
            "mp integer",
            "per numeric",
            "ts_pct numeric",
            "orb_pct numeric",
            "usg_pct numeric",
            "fg3a_per_fga_pct numeric",
            "fta_per_fga_pct numeric",
        ]
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


def _insert_clean_dataset(
    session: Session,
    *,
    omit_source_team_code_tables: set[str] | None = None,
) -> None:
    omitted = omit_source_team_code_tables or set()
    session.execute(
        text(
            "insert into core.seasons (id, season_year, league, label) "
            "values (1, 2021, 'NBA', '2020-21'), (2, 2024, 'NBA', '2023-24')"
        )
    )
    session.execute(
        text(
            "insert into core.teams "
            "(id, basketball_reference_team_id, current_abbreviation, current_name) values "
            "(1, 'BOS', 'BOS', 'Boston Celtics'), "
            "(2, 'HOU', 'HOU', 'Houston Rockets'), "
            "(3, 'BRK', 'BRK', 'Brooklyn Nets')"
        )
    )
    session.execute(
        text(
            "insert into core.team_aliases (id, team_id, abbreviation) values "
            "(1, 1, 'BOS'), (2, 2, 'HOU'), (3, 3, 'BRK')"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values "
            "(1, 1, 2, 'BOS'), "
            "(2, 2, 1, 'HOU'), "
            "(3, 3, 1, 'BRK')"
        )
    )
    session.execute(
        text(
            "insert into core.players (id, basketball_reference_player_id, full_name) values "
            "(1, 'brownja02', 'Jaylen Brown'), "
            "(2, 'hardeja01', 'James Harden')"
        )
    )
    session.execute(
        text(
            "insert into core.player_seasons (id, player_id, season_id) values "
            "(1, 1, 2), (2, 2, 1)"
        )
    )
    session.execute(
        text(
            "insert into core.player_team_seasons (id, player_season_id, team_season_id) values "
            "(1, 1, 1), (2, 2, 2), (3, 2, 3)"
        )
    )

    for spec in STATS_TABLE_SPECS:
        grains = _grains_for_spec(spec)
        for row_id, grain in enumerate(grains, start=1):
            params = _stats_row_params(spec, grain)
            if spec.table_name in omitted:
                params.pop("source_team_code", None)
            params["id"] = row_id
            params[spec.grain_column] = grain
            columns = ", ".join(params)
            values = ", ".join(f":{column}" for column in params)
            session.execute(
                text(f"insert into stats.{spec.table_name} ({columns}) values ({values})"),
                params,
            )


def _grains_for_spec(spec) -> list[int]:
    if spec.family == "team_stint" and spec.season_type == "regular":
        return [1, 2, 3]
    if spec.family == "team_stint" and spec.season_type == "postseason":
        return [1, 3]
    return [1, 2]


def _stats_row_params(spec, grain: int) -> dict[str, object]:
    if spec.season_type == "postseason":
        base = {
            "source_url": "https://example.test/players/sample.html#playoffs",
            "cache_path": "cache/player_postseason.html.gz",
            "parser_version": "player-page-postseason-parser-v1",
        }
    elif spec.family == "aggregate":
        base = {
            "source_url": "https://example.test/players/sample.html",
            "cache_path": "cache/player_regular.html.gz",
            "parser_version": "player-page-parser-v1",
        }
    else:
        base = {
            "source_url": "https://example.test/teams/sample/2024.html",
            "cache_path": "cache/team_regular.html.gz",
            "parser_version": "stats-parser-v1",
        }

    if spec.family == "aggregate":
        if spec.season_type == "regular":
            base["source_team_code"] = "BOS" if grain == 1 else "2TM"
        else:
            base["source_team_code"] = "BOS" if grain == 1 else "BRK"

    if spec.table_name == "player_team_season_roster":
        return {
            **base,
            "jersey_number": "7" if grain == 1 else "13",
            "player_name": "Jaylen Brown" if grain == 1 else "James Harden",
            "position": "SG",
            "weight": 220,
        }
    if spec.table_name.endswith("_totals"):
        return {**base, "age": 27, "g": 82 if grain != 2 else 44, "gs": 82 if grain == 1 else 36, "mp": 2800 if grain == 1 else 1500, "fg_pct": 0.5, "pts": 2000 if grain == 1 else 1080}
    if spec.table_name.endswith("_per_game"):
        return {**base, "age": 27, "g": 82 if grain != 2 else 44, "gs": 82 if grain == 1 else 36, "mp_per_game": 34.2, "fg_pct": 0.5}
    if spec.table_name.endswith("_per_minute"):
        return {**base, "age": 27, "g": 82 if grain != 2 else 44, "gs": 82 if grain == 1 else 36, "mp": 2800 if grain == 1 else 1500, "fg_pct": 0.5}
    if spec.table_name.endswith("_per_poss"):
        return {**base, "age": 27, "g": 82 if grain != 2 else 44, "gs": 82 if grain == 1 else 36, "mp": 2800 if grain == 1 else 1500, "fg_pct": 0.5, "ortg": 118, "drtg": 109}
    if spec.table_name.endswith("_advanced"):
        return {
            **base,
            "age": 27,
            "g": 82 if grain != 2 else 44,
            "gs": 82 if grain == 1 else 36,
            "mp": 2800 if grain == 1 else 1500,
            "per": 22.1,
            "ts_pct": 0.61,
            "orb_pct": 7.5,
            "usg_pct": 29.4,
            "fg3a_per_fga_pct": 0.42,
            "fta_per_fga_pct": 0.31,
        }
    if spec.table_name.endswith("_adj_shooting"):
        return {
            **base,
            "age": 27,
            "g": 82 if grain != 2 else 44,
            "gs": 82 if grain == 1 else 36,
            "mp": 2800 if grain == 1 else 1500,
            "fg_pct": 0.5,
            "adj_fg_pct": 108.0,
            "ts_pct": 0.61,
            "adj_ts_pct": 114.0,
        }
    if spec.table_name.endswith("_shooting"):
        return {**base, "age": 27, "g": 82 if grain != 2 else 44, "gs": 82 if grain == 1 else 36, "mp": 2800 if grain == 1 else 1500, "fg_pct": 0.5, "avg_dist": 14.2}
    if spec.table_name.endswith("_pbp"):
        return {**base, "age": 27, "g": 82 if grain != 2 else 44, "gs": 82 if grain == 1 else 36, "mp": 2800 if grain == 1 else 1500, "pct_pg": 40.0, "net_plus_minus": 8.5}
    raise AssertionError(f"Unhandled stats row {spec.table_name}")


def _expected_loaded_rows() -> int:
    return 75


def _stats_backfill_report(
    *,
    stats_loaded_rows: int,
    processing_failed_sources: int = 0,
    stats_failed_rows: int = 0,
    stats_quarantined_rows: int = 0,
) -> dict[str, object]:
    return {
        "selected_sources": 5,
        "processed_sources": 5,
        "processing_failed_sources": processing_failed_sources,
        "stats_loaded_rows": stats_loaded_rows,
        "stats_skipped_rows": 0,
        "stats_failed_rows": stats_failed_rows,
        "stats_quarantined_rows": stats_quarantined_rows,
    }


def _issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}
