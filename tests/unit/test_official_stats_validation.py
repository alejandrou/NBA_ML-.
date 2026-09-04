from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from click import unstyle
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.validation.official_stats import (
    POSTSEASON_AGGREGATE_TABLE_SPECS,
    POSTSEASON_TEAM_STINT_TABLE_SPECS,
    REGULAR_AGGREGATE_TABLE_SPECS,
    REGULAR_TEAM_STINT_TABLE_SPECS,
    STATS_TABLE_SPECS,
    _backfill_report_issues,
    _extract_backfill_summary,
    validate_official_stats,
)
from nba_data.validation.parser_contracts import current_parser_version
from nba_data.validation.stats_coverage import compute_cache_fingerprint


@pytest.fixture
def session() -> Iterator[Session]:
    with _session_with_schema() as test_session:
        yield test_session


@pytest.mark.unit
def test_validate_official_stats_accepts_clean_final_phase_4e_shape(session: Session) -> None:
    _insert_clean_dataset(session)

    reports = _stats_backfill_reports()
    report = validate_official_stats(
        session, reports, coverage_artifact=_coverage_artifact_for_clean_dataset()
    )

    assert report.passed is True
    assert len(report.table_counts) == len(STATS_TABLE_SPECS)
    assert report.table_counts["stats.player_team_season_roster"] == 3
    assert report.table_counts["stats.player_season_totals"] == 2
    assert report.table_counts["stats.player_postseason_totals"] == 2
    assert report.validation_summary["synthetic_code_violations"] == 0
    assert report.validation_summary["numeric_range_violations"] == 0
    assert report.validation_summary["parser_lineage_violations"] == 0
    assert report.backfill_summary["team_stats"]["stats_loaded_rows"] == 30  # type: ignore[index]
    assert report.backfill_summary["player_stats"]["cache_root"] == str(Path.cwd())  # type: ignore[index]
    assert report.backfill_summary["player_postseason_stats"]["discovery_status"] == "ok"  # type: ignore[index]
    assert report.to_dict()["issues"] == []


@pytest.mark.unit
def test_backfill_reports_reconcile_the_expected_archive_total() -> None:
    reports = _stats_backfill_reports(
        team_rows=129_000,
        player_rows=96_336,
        postseason_aggregate_rows=40_528,
        postseason_team_rows=40_528,
    )
    summary = _extract_backfill_summary(reports)

    issues = _backfill_report_issues(
        {"stats.synthetic": 306_392},
        summary,
        reports,
    )

    assert issues == []


@pytest.mark.unit
def test_backfill_report_set_names_missing_producers() -> None:
    reports = _stats_backfill_reports()
    reports.pop("player_stats")

    issues = _backfill_report_issues(
        {"stats.synthetic": _expected_loaded_rows()},
        _extract_backfill_summary(reports),
        reports,
    )

    missing = [issue for issue in issues if issue.code == "stats_backfill_report_missing_producer"]
    assert len(missing) == 1
    assert missing[0].context["missing_producers"] == ["player_stats"]


@pytest.mark.unit
def test_backfill_report_vocabularies_are_selected_by_producer_kind() -> None:
    reports = {"team_stats": _player_stats_report(rows_loaded_or_updated=75)}

    issues = _backfill_report_issues(
        {"stats.synthetic": 75},
        _extract_backfill_summary(reports),
        reports,
    )

    missing_fields = [
        issue.context["field"]
        for issue in issues
        if issue.code == "stats_backfill_report_missing_field"
    ]
    assert "stats_loaded_rows" in missing_fields


@pytest.mark.unit
def test_backfill_report_failure_counters_are_validated() -> None:
    reports = _stats_backfill_reports()
    reports["player_stats"]["rows_failed"] = 2

    issues = _backfill_report_issues(
        {"stats.synthetic": _expected_loaded_rows()},
        _extract_backfill_summary(reports),
        reports,
    )

    assert any(issue.code == "backfill_failures_present" for issue in issues)

    reports["player_stats"].pop("entries_failed")
    reports["player_stats"].pop("rows_failed")
    issues = _backfill_report_issues(
        {"stats.synthetic": _expected_loaded_rows()},
        _extract_backfill_summary(reports),
        reports,
    )
    assert any(issue.code == "stats_backfill_report_missing_failure_counter" for issue in issues)


@pytest.mark.unit
def test_team_report_requires_new_explicit_failure_counters() -> None:
    reports = _stats_backfill_reports()
    reports["team_stats"].pop("entries_failed")
    reports["team_stats"].pop("rows_failed")

    issues = _backfill_report_issues(
        {"stats.synthetic": _expected_loaded_rows()},
        _extract_backfill_summary(reports),
        reports,
    )

    missing_counters = {
        issue.context["counter"]
        for issue in issues
        if issue.code == "stats_backfill_report_missing_failure_counter"
    }
    assert {"entries_failed", "rows_failed"} <= missing_counters


@pytest.mark.unit
def test_backfill_report_counts_must_be_non_negative_integers() -> None:
    reports = _stats_backfill_reports()
    reports["team_stats"]["stats_loaded_rows"] = 30.5
    reports["player_stats"]["rows_failed"] = 0.5

    issues = _backfill_report_issues(
        {"stats.synthetic": _expected_loaded_rows()},
        _extract_backfill_summary(reports),
        reports,
    )

    assert any(
        issue.code == "stats_backfill_report_invalid_field"
        and issue.context["field"] == "stats_loaded_rows"
        for issue in issues
    )
    assert any(
        issue.code == "stats_backfill_report_invalid_failure_counter"
        and issue.context["counter"] == "rows_failed"
        for issue in issues
    )


@pytest.mark.unit
def test_player_report_metadata_is_validated_without_affecting_row_totals() -> None:
    reports = _stats_backfill_reports()
    reports["player_stats"]["cache_root"] = "relative/cache"
    reports["player_postseason_stats"]["discovery_status"] = "unknown"

    issues = _backfill_report_issues(
        {"stats.synthetic": _expected_loaded_rows()},
        _extract_backfill_summary(reports),
        reports,
    )

    metadata_issues = [
        issue for issue in issues if issue.code == "stats_backfill_report_invalid_metadata"
    ]
    assert {issue.context["field"] for issue in metadata_issues} == {
        "cache_root",
        "discovery_status",
    }


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
            "'cache/player_postseason.html.gz', 'player-page-postseason-parser-v4', 31, 12, 12, 39.4, 0.50)"
        )
    )
    session.execute(
        text(
            "insert into stats.player_postseason_totals "
            "(id, player_season_id, source_team_code, source_url, cache_path, parser_version, age, g, gs, mp, fg_pct, pts) "
            "values (99, 999, 'BRK', 'https://example.test/players/h/hardenja01.html#playoffs', "
            "'cache/player_postseason.html.gz', 'player-page-postseason-parser-v4', 31, 12, 12, 420, 0.50, 320)"
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
            "'cache/player_postseason.html.gz', 'player-page-postseason-parser-v4', 31, 12, 12, 420, 0.50, 320)"
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
def test_validate_official_stats_detects_a_marker_outside_the_old_literal_set(
    session: Session,
) -> None:
    """`5TM` exists in the cached archive; the validator must not wave it through."""

    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.teams "
            "(id, basketball_reference_team_id, current_abbreviation, current_name) "
            "values (9, '5TM', '5TM', 'Synthetic Team')"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values (9, 9, 1, '5TM')"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert {
        "synthetic_code_in_core_teams",
        "synthetic_code_in_core_team_seasons",
    } <= _issue_codes(report)


@pytest.mark.unit
@pytest.mark.parametrize("marker", ["2TM", "3TM", "4TM", "5TM", "6TM", "10TM"])
def test_validate_official_stats_accepts_any_marker_as_an_aggregate_source(
    session: Session, marker: str
) -> None:
    """A marker is a legitimate aggregate `source_team_code`, per ADR 0007."""

    _insert_clean_dataset(session)
    session.execute(
        text("update stats.player_season_totals set source_team_code = :code"),
        {"code": marker},
    )

    report = validate_official_stats(session)

    assert "invalid_aggregate_source_team_code" not in _issue_codes(report)


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

    report = validate_official_stats(
        session, coverage_artifact=_coverage_artifact_for_clean_dataset()
    )

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
def test_validate_official_stats_detects_unknown_parser_version(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_season_totals set parser_version = 'not-a-real-parser' "
            "where player_season_id = 1"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert "unknown_parser_version" in _issue_codes(report)
    issue = next(i for i in report.issues if i.code == "unknown_parser_version")
    assert issue.context["table"] == "stats.player_season_totals"
    assert issue.context["parser_version"] == "not-a-real-parser"
    assert issue.context["count"] == 1
    assert issue.context["examples"] == [1]
    assert report.validation_summary["parser_lineage_violations"] >= 1


@pytest.mark.unit
def test_validate_official_stats_detects_stale_parser_version(session: Session) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_season_totals set parser_version = 'player-page-parser-v2' "
            "where player_season_id = 1"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert "stale_parser_version" in _issue_codes(report)
    issue = next(i for i in report.issues if i.code == "stale_parser_version")
    assert issue.context["table"] == "stats.player_season_totals"
    assert issue.context["parser_version"] == "player-page-parser-v2"
    assert issue.context["count"] == 1


@pytest.mark.unit
def test_validate_official_stats_groups_parser_lineage_violations_by_table_and_version(
    session: Session,
) -> None:
    """Mixed unknown/stale versions across two tables group into separate issues."""

    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_season_totals set parser_version = 'player-page-parser-v1' "
            "where player_season_id = 1"
        )
    )
    session.execute(
        text(
            "update stats.player_team_season_totals set parser_version = 'legacy-parser' "
            "where player_team_season_id = 1"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    stale = [issue for issue in report.issues if issue.code == "stale_parser_version"]
    unknown = [issue for issue in report.issues if issue.code == "unknown_parser_version"]
    assert {issue.context["table"] for issue in stale} == {"stats.player_season_totals"}
    assert {issue.context["table"] for issue in unknown} == {"stats.player_team_season_totals"}
    assert report.validation_summary["parser_lineage_violations"] == len(stale) + len(unknown)


@pytest.mark.unit
def test_validate_official_stats_rejects_a_current_version_from_the_wrong_producer(
    session: Session,
) -> None:
    """A registered, current identifier is still wrong if another producer owns it.

    `team-season-parser-v1` is current for `team_season`, but
    `stats.player_season_totals` is written by the `player_page_regular`
    backfill. Stamping the team-season identifier there must not pass simply
    because that identifier is globally current.
    """

    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_season_totals set parser_version = 'team-season-parser-v1' "
            "where player_season_id = 1"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert "wrong_producer_parser_version" in _issue_codes(report)
    issue = next(i for i in report.issues if i.code == "wrong_producer_parser_version")
    assert issue.context["table"] == "stats.player_season_totals"
    assert issue.context["parser_version"] == "team-season-parser-v1"
    assert issue.context["count"] == 1
    assert issue.context["examples"] == [1]
    assert report.validation_summary["parser_lineage_violations"] >= 1
    assert "unknown_parser_version" not in _issue_codes(report)
    assert "stale_parser_version" not in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_rejects_a_stale_version_from_the_wrong_producer(
    session: Session,
) -> None:
    """Wrong-producer classification wins over staleness for the same value."""

    _insert_clean_dataset(session)
    session.execute(
        text(
            "update stats.player_team_season_totals set parser_version = "
            "'player-page-postseason-parser-v1' where player_team_season_id = 1"
        )
    )

    report = validate_official_stats(session)

    assert report.passed is False
    assert "wrong_producer_parser_version" in _issue_codes(report)
    issue = next(i for i in report.issues if i.code == "wrong_producer_parser_version")
    assert issue.context["table"] == "stats.player_team_season_totals"
    assert "stale_parser_version" not in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_detects_duplicate_rows(session: Session) -> None:
    with _session_with_schema(no_unique_grain_tables={"player_team_season_totals"}) as test_session:
        _insert_clean_dataset(test_session)
        test_session.execute(
            text(
                "insert into stats.player_team_season_totals "
                "(id, player_team_season_id, source_url, cache_path, parser_version, age, g, gs, mp, fg_pct, pts) "
                "values (99, 1, 'dup', 'dup', 'team-season-parser-v1', 27, 82, 82, 2900, 0.51, 2100)"
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
    backfill_report = tmp_path / "team-stats-backfill.json"
    backfill_report.write_text(
        json.dumps(_team_stats_report(stats_loaded_rows=75)),
        encoding="utf-8",
    )

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

    def fake_validate(
        session: object,
        backfill_data: object,
        *,
        coverage_artifact: object = None,
        coverage_cache_root: object = None,
    ) -> FakeValidationReport:
        assert session is fake_session
        assert backfill_data == {"team_stats": _team_stats_report(stats_loaded_rows=75)}
        assert coverage_artifact is None
        assert coverage_cache_root is None
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
            "--team-stats-report",
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


@pytest.mark.unit
def test_cli_validate_official_stats_rejects_removed_single_report_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("the removed option must fail before database creation")

    monkeypatch.setattr("nba_data.cli.main.create_db_engine", fail_engine)
    report_path = tmp_path / "stats-backfill.json"
    report_path.write_text("{}", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "official-stats",
            "--stats-backfill-report",
            str(report_path),
        ],
    )

    assert result.exit_code != 0
    assert "--team-stats-report" in unstyle(result.output)


@pytest.mark.unit
def test_cli_validate_official_stats_rejects_duplicate_producer_report_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("duplicate report options must fail before database creation")

    monkeypatch.setattr("nba_data.cli.main.create_db_engine", fail_engine)
    first_report = tmp_path / "team-stats-first.json"
    second_report = tmp_path / "team-stats-second.json"
    first_report.write_text("{}", encoding="utf-8")
    second_report.write_text("{}", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "official-stats",
            "--team-stats-report",
            str(first_report),
            "--team-stats-report",
            str(second_report),
        ],
    )

    assert result.exit_code != 0
    assert "--team-stats-report accepts at most one path" in unstyle(result.output)


# --- F4E-018 coverage comparison -------------------------------------------------


@pytest.mark.unit
def test_validate_official_stats_coverage_passes_on_matching_artifact(session: Session) -> None:
    _insert_clean_dataset(session)

    report = validate_official_stats(
        session, coverage_artifact=_coverage_artifact_for_clean_dataset()
    )

    assert report.passed is True
    assert report.coverage_summary["status"] == "loaded"
    assert report.coverage_summary["freshness_status"] == "unverified"
    dimensions = report.coverage_summary["dimensions"]
    for name in (
        "regular_aggregate",
        "postseason_aggregate",
        "regular_team_stint",
        "postseason_team_stint",
    ):
        assert dimensions[name]["missing"] == 0
        assert dimensions[name]["unexpected"] == 0
        assert dimensions[name]["scope"]["league"] == "NBA"
        assert dimensions[name]["scope"]["season_years"] == [2021, 2024]
        assert dimensions[name]["scope"]["excluded_entries"] == 0


@pytest.mark.unit
def test_validate_official_stats_coverage_missing_artifact_still_runs_the_rest_of_validation(
    session: Session,
) -> None:
    _insert_clean_dataset(session)

    report = validate_official_stats(session)

    assert report.passed is False
    assert "coverage_artifact_missing" in _issue_codes(report)
    assert report.coverage_summary == {"status": "missing"}
    assert report.validation_summary["coverage_violations"] == 1
    # The rest of the report still ran and is still complete.
    assert set(report.table_counts) == {f"stats.{spec.table_name}" for spec in STATS_TABLE_SPECS}


@pytest.mark.unit
def test_validate_official_stats_coverage_rejects_unsupported_schema_version(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    artifact["schema_version"] = 2

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_artifact_schema_unsupported" in _issue_codes(report)
    assert "dimensions" not in report.coverage_summary


@pytest.mark.unit
def test_validate_official_stats_coverage_rejects_a_malformed_artifact_shape(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    del artifact["cache_fingerprint"]

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_artifact_invalid" in _issue_codes(report)
    assert "dimensions" not in report.coverage_summary


@pytest.mark.unit
def test_validate_official_stats_coverage_verifies_a_matching_fingerprint(
    session: Session, tmp_path: Path
) -> None:
    _insert_clean_dataset(session)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    artifact = _coverage_artifact_for_clean_dataset()
    artifact["cache_fingerprint"] = compute_cache_fingerprint(cache_root).to_dict()

    report = validate_official_stats(
        session, coverage_artifact=artifact, coverage_cache_root=cache_root
    )

    assert report.passed is True
    assert report.coverage_summary["freshness_status"] == "verified"


@pytest.mark.unit
def test_validate_official_stats_coverage_detects_a_stale_fingerprint(
    session: Session, tmp_path: Path
) -> None:
    _insert_clean_dataset(session)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    artifact = _coverage_artifact_for_clean_dataset()
    artifact["cache_fingerprint"] = {"digest": "f" * 64, "player_page_count": 0, "team_page_count": 0}

    report = validate_official_stats(
        session, coverage_artifact=artifact, coverage_cache_root=cache_root
    )

    assert report.passed is False
    assert "coverage_artifact_stale" in _issue_codes(report)
    assert "dimensions" not in report.coverage_summary
    # No key comparison ran once the fingerprint mismatched.
    assert "coverage_missing_regular_aggregate_row" not in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_coverage_reports_unexplained_source_seasons(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    artifact["unexplained"] = [
        {
            "basketball_reference_player_id": "hardeja01",
            "season_year": 2021,
            "season_type": "regular",
            "source_table": "totals",
            "reason": "ambiguous_multiple_real_team_rows_without_marker",
        }
    ]

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_unexplained_source" in _issue_codes(report)
    issue = next(i for i in report.issues if i.code == "coverage_unexplained_source")
    assert issue.context["count"] == 1


@pytest.mark.unit
def test_validate_official_stats_coverage_reports_source_issues_as_a_degraded_oracle(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    artifact["source_issues"] = [
        {
            "cache_path": "/cache/players-h-hardeja01.html-deadbeef.html.gz",
            "status": "invalid_or_unreadable",
            "error_message": "truncated gzip",
        }
    ]

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_source_issues_present" in _issue_codes(report)
    issue = next(i for i in report.issues if i.code == "coverage_source_issues_present")
    assert issue.context["count"] == 1


@pytest.mark.unit
def test_validate_official_stats_coverage_detects_missing_and_unexpected_regular_aggregate_rows(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "brownja02", 2024)
    entry["regular_aggregate_tables"] = [
        table for table in entry["regular_aggregate_tables"] if table != "stats.player_season_totals"
    ]
    artifact["entries"].append(_fake_aggregate_entry("ghostpl01", 2021, "stats.player_season_totals"))

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_missing_regular_aggregate_row" in _issue_codes(report)
    assert "coverage_unexpected_regular_aggregate_row" in _issue_codes(report)
    missing = next(i for i in report.issues if i.code == "coverage_missing_regular_aggregate_row")
    assert missing.context["examples"] == [
        {"basketball_reference_player_id": "ghostpl01", "season_year": 2021, "table": "stats.player_season_totals"}
    ]
    unexpected = next(i for i in report.issues if i.code == "coverage_unexpected_regular_aggregate_row")
    assert unexpected.context["examples"] == [
        {"basketball_reference_player_id": "brownja02", "season_year": 2024, "table": "stats.player_season_totals"}
    ]


@pytest.mark.unit
def test_validate_official_stats_coverage_detects_missing_and_unexpected_postseason_aggregate_rows(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "brownja02", 2024)
    entry["postseason_aggregate_tables"] = [
        table
        for table in entry["postseason_aggregate_tables"]
        if table != "stats.player_postseason_totals"
    ]
    artifact["entries"].append(
        _fake_aggregate_entry("ghostpl01", 2021, "stats.player_postseason_totals", postseason=True)
    )

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_missing_postseason_aggregate_row" in _issue_codes(report)
    assert "coverage_unexpected_postseason_aggregate_row" in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_coverage_reports_a_missing_in_range_persisted_key(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text("delete from stats.player_season_totals where player_season_id = 1")
    )

    report = validate_official_stats(
        session, coverage_artifact=_coverage_artifact_for_clean_dataset()
    )

    assert report.passed is False
    issue = next(i for i in report.issues if i.code == "coverage_missing_regular_aggregate_row")
    assert issue.context["examples"] == [
        {
            "basketball_reference_player_id": "brownja02",
            "season_year": 2024,
            "table": "stats.player_season_totals",
        }
    ]


@pytest.mark.unit
def test_validate_official_stats_coverage_scopes_expected_keys_to_database_seasons(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.seasons (id, season_year, league, label) values "
            "(3, 2000, 'NBA', '1999-00'), (4, 2025, 'NBA', '2024-25')"
        )
    )
    artifact = _coverage_artifact_for_clean_dataset()
    artifact["entries"].extend(
        _fake_aggregate_entry("ghostpl01", season_year, "stats.player_season_totals")
        for season_year in (1999, 2000, 2025, 2026)
    )

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    issue = next(i for i in report.issues if i.code == "coverage_missing_regular_aggregate_row")
    assert issue.context["examples"] == [
        {
            "basketball_reference_player_id": "ghostpl01",
            "season_year": 2000,
            "table": "stats.player_season_totals",
        },
        {
            "basketball_reference_player_id": "ghostpl01",
            "season_year": 2025,
            "table": "stats.player_season_totals",
        },
    ]
    scope = report.coverage_summary["dimensions"]["regular_aggregate"]["scope"]
    assert scope == {
        "league": "NBA",
        "season_years": [2000, 2021, 2024, 2025],
        "artifact_entries": 6,
        "in_scope_entries": 4,
        "excluded_entries": 2,
        "excluded_seasons": [1999, 2026],
        "excluded_expected_keys": 2,
        "excluded_reason": "season_not_loaded_for_league",
    }


@pytest.mark.unit
def test_validate_official_stats_coverage_fails_on_an_empty_nba_scope(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    session.execute(text("update core.seasons set league = 'WNBA'"))

    report = validate_official_stats(
        session, coverage_artifact=_coverage_artifact_for_clean_dataset()
    )

    assert report.passed is False
    issue = next(i for i in report.issues if i.code == "coverage_scope_empty")
    assert issue.context == {
        "count": 1,
        "league": "NBA",
        "season_years": [],
    }
    assert report.validation_summary["coverage_violations"] == 1
    dimensions = report.coverage_summary["dimensions"]
    for dimension in dimensions.values():
        assert dimension["scope"]["season_years"] == []


@pytest.mark.unit
def test_validate_official_stats_coverage_does_not_use_a_non_nba_collision_row(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.seasons (id, season_year, league, label) values "
            "(3, 2024, 'WNBA', '2024')"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons "
            "(id, team_id, season_id, team_abbreviation) values "
            "(4, 1, 3, 'BOS')"
        )
    )
    session.execute(
        text("insert into core.player_seasons (id, player_id, season_id) values (3, 1, 3)")
    )
    session.execute(
        text(
            "insert into core.player_team_seasons "
            "(id, player_season_id, team_season_id) values (4, 3, 4)"
        )
    )
    session.execute(
        text("delete from stats.player_season_totals where player_season_id = 1")
    )
    session.execute(
        text("delete from stats.player_team_season_totals where player_team_season_id = 1")
    )
    spec = REGULAR_AGGREGATE_TABLE_SPECS[0]
    params = _stats_row_params(spec, grain=3)
    params.update({"id": 99, spec.grain_column: 3})
    columns = ", ".join(params)
    values = ", ".join(f":{column}" for column in params)
    session.execute(
        text(f"insert into stats.{spec.table_name} ({columns}) values ({values})"),
        params,
    )
    stint_spec = REGULAR_TEAM_STINT_TABLE_SPECS[1]
    stint_params = _stats_row_params(stint_spec, grain=4)
    stint_params.update({"id": 99, stint_spec.grain_column: 4})
    stint_columns = ", ".join(stint_params)
    stint_values = ", ".join(f":{column}" for column in stint_params)
    session.execute(
        text(
            f"insert into stats.{stint_spec.table_name} "
            f"({stint_columns}) values ({stint_values})"
        ),
        stint_params,
    )

    report = validate_official_stats(
        session, coverage_artifact=_coverage_artifact_for_clean_dataset()
    )

    assert report.passed is False
    issue = next(i for i in report.issues if i.code == "coverage_missing_regular_aggregate_row")
    assert issue.context["examples"] == [
        {
            "basketball_reference_player_id": "brownja02",
            "season_year": 2024,
            "table": "stats.player_season_totals",
        }
    ]
    stint_issue = next(i for i in report.issues if i.code == "coverage_missing_regular_team_stint_row")
    assert stint_issue.context["examples"] == [
        {
            "basketball_reference_player_id": "brownja02",
            "season_year": 2024,
            "team_code": "BOS",
            "table": "stats.player_team_season_totals",
        }
    ]
    assert "coverage_unexpected_regular_aggregate_row" not in _issue_codes(report)
    assert "coverage_unexpected_regular_team_stint_row" not in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_coverage_does_not_allow_persisted_nba_rows_without_artifact_expectations(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    session.execute(
        text(
            "insert into core.seasons (id, season_year, league, label) values "
            "(3, 2026, 'NBA', '2025-26')"
        )
    )
    session.execute(
        text("insert into core.player_seasons (id, player_id, season_id) values (3, 1, 3)")
    )
    spec = REGULAR_AGGREGATE_TABLE_SPECS[0]
    params = _stats_row_params(spec, grain=1)
    params.update({"id": 99, spec.grain_column: 3})
    columns = ", ".join(params)
    values = ", ".join(f":{column}" for column in params)
    session.execute(
        text(f"insert into stats.{spec.table_name} ({columns}) values ({values})"),
        params,
    )

    report = validate_official_stats(
        session, coverage_artifact=_coverage_artifact_for_clean_dataset()
    )

    assert report.passed is False
    issue = next(i for i in report.issues if i.code == "coverage_unexpected_regular_aggregate_row")
    assert issue.context["examples"] == [
        {
            "basketball_reference_player_id": "brownja02",
            "season_year": 2026,
            "table": "stats.player_season_totals",
        }
    ]


@pytest.mark.unit
def test_validate_official_stats_coverage_scopes_regular_team_stints_without_changing_actual_rows(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    artifact["entries"].append(
        {
            "basketball_reference_player_id": "ghostpl01",
            "season_year": 1999,
            "regular_aggregate_tables": [],
            "postseason_aggregate_tables": [],
            "regular_team_stints": [
                {"team_code": "BOS", "table": spec.full_name}
                for spec in REGULAR_TEAM_STINT_TABLE_SPECS
            ],
            "postseason_team_stints": [],
            "did_not_play": {"regular": False, "postseason": False},
        }
    )

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is True
    dimension = report.coverage_summary["dimensions"]["regular_team_stint"]
    assert dimension["expected"] == dimension["actual"] == 27
    assert dimension["missing"] == dimension["unexpected"] == 0
    assert dimension["scope"]["excluded_entries"] == 1
    assert dimension["scope"]["excluded_seasons"] == [1999]
    assert dimension["scope"]["excluded_expected_keys"] == len(REGULAR_TEAM_STINT_TABLE_SPECS)


@pytest.mark.unit
def test_validate_official_stats_coverage_detects_missing_and_unexpected_regular_team_stint_rows(
    session: Session,
) -> None:
    """Same player/season/team on both sides, but a different table each — the
    wrong-stats-family case: table is part of the key, so this is not a match."""

    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "brownja02", 2024)
    entry["regular_team_stints"] = [
        stint for stint in entry["regular_team_stints"] if stint["table"] != "stats.player_team_season_totals"
    ]
    entry["regular_team_stints"].append({"team_code": "BOS", "table": "stats.player_team_season_pbp_ghost"})

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_missing_regular_team_stint_row" in _issue_codes(report)
    assert "coverage_unexpected_regular_team_stint_row" in _issue_codes(report)
    missing = next(i for i in report.issues if i.code == "coverage_missing_regular_team_stint_row")
    assert missing.context["examples"] == [
        {
            "basketball_reference_player_id": "brownja02",
            "season_year": 2024,
            "team_code": "BOS",
            "table": "stats.player_team_season_pbp_ghost",
        }
    ]
    unexpected = next(i for i in report.issues if i.code == "coverage_unexpected_regular_team_stint_row")
    assert unexpected.context["examples"] == [
        {
            "basketball_reference_player_id": "brownja02",
            "season_year": 2024,
            "team_code": "BOS",
            "table": "stats.player_team_season_totals",
        }
    ]


@pytest.mark.unit
def test_validate_official_stats_coverage_detects_missing_and_unexpected_postseason_team_stint_rows(
    session: Session,
) -> None:
    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "hardeja01", 2021)
    entry["postseason_team_stints"] = [
        stint
        for stint in entry["postseason_team_stints"]
        if stint["table"] != "stats.player_team_postseason_totals"
    ]
    entry["postseason_team_stints"].append(
        {"team_code": "BRK", "table": "stats.player_team_postseason_pbp_ghost"}
    )

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is False
    assert "coverage_missing_postseason_team_stint_row" in _issue_codes(report)
    assert "coverage_unexpected_postseason_team_stint_row" in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_coverage_did_not_play_regular_still_verifies_other_dimensions(
    session: Session,
) -> None:
    """A regular DNP season only suppresses the regular aggregate expectation.

    Team stints (regular and postseason) and the postseason aggregate stay
    independently verified — a regular DNP season may legitimately carry
    postseason rows, and DNP evidence never prohibits roster/team-stint rows.
    """

    _insert_clean_dataset(session)
    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "hardeja01", 2021)
    entry["regular_aggregate_tables"] = []
    entry["did_not_play"] = {"regular": True, "postseason": False}

    report = validate_official_stats(session, coverage_artifact=artifact)

    # The DB still has real regular aggregate rows for hardeja01/2021, so
    # withdrawing the expectation now makes every one of them unexpected.
    assert report.passed is False
    assert "coverage_unexpected_regular_aggregate_row" in _issue_codes(report)
    assert "coverage_missing_regular_team_stint_row" not in _issue_codes(report)
    assert "coverage_unexpected_regular_team_stint_row" not in _issue_codes(report)
    assert "coverage_missing_postseason_aggregate_row" not in _issue_codes(report)
    assert "coverage_unexpected_postseason_aggregate_row" not in _issue_codes(report)
    assert "coverage_missing_postseason_team_stint_row" not in _issue_codes(report)
    assert "coverage_unexpected_postseason_team_stint_row" not in _issue_codes(report)


def _delete_regular_aggregate_rows(session: Session, player_season_id: int) -> None:
    for spec in REGULAR_AGGREGATE_TABLE_SPECS:
        session.execute(
            text(f"delete from stats.{spec.table_name} where {spec.grain_column} = :grain"),
            {"grain": player_season_id},
        )


def _delete_regular_team_stint_rows(session: Session, player_team_season_ids: tuple[int, ...]) -> None:
    placeholders = ", ".join(f":grain{i}" for i in range(len(player_team_season_ids)))
    params = {f"grain{i}": grain for i, grain in enumerate(player_team_season_ids)}
    for spec in REGULAR_TEAM_STINT_TABLE_SPECS:
        session.execute(
            text(f"delete from stats.{spec.table_name} where {spec.grain_column} in ({placeholders})"),
            params,
        )


@pytest.mark.unit
def test_validate_official_stats_coverage_passes_a_valid_postseason_only_season(session: Session) -> None:
    """A season with no regular-season presence at all (no aggregate, no roster
    row) but a real postseason presence is not itself a violation -- the
    artifact simply carries empty regular expectations for that season, and
    the DB agrees.
    """

    _insert_clean_dataset(session)
    _delete_regular_aggregate_rows(session, player_season_id=2)
    _delete_regular_team_stint_rows(session, player_team_season_ids=(2, 3))

    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "hardeja01", 2021)
    entry["regular_aggregate_tables"] = []
    entry["regular_team_stints"] = []

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is True
    assert "coverage_missing_regular_aggregate_row" not in _issue_codes(report)
    assert "coverage_unexpected_regular_aggregate_row" not in _issue_codes(report)
    assert "coverage_missing_regular_team_stint_row" not in _issue_codes(report)
    assert "coverage_unexpected_regular_team_stint_row" not in _issue_codes(report)
    assert "coverage_missing_postseason_aggregate_row" not in _issue_codes(report)
    assert "coverage_unexpected_postseason_aggregate_row" not in _issue_codes(report)


@pytest.mark.unit
def test_validate_official_stats_coverage_passes_did_not_play_regular_plus_real_postseason(
    session: Session,
) -> None:
    """A regular did-not-play season with a genuine postseason call-up: no
    regular presence of any kind, `did_not_play.regular` set, and the DB
    agrees on every dimension -- this must pass cleanly, unlike the
    deliberately-mismatched DNP test above.
    """

    _insert_clean_dataset(session)
    _delete_regular_aggregate_rows(session, player_season_id=2)
    _delete_regular_team_stint_rows(session, player_team_season_ids=(2, 3))

    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "hardeja01", 2021)
    entry["regular_aggregate_tables"] = []
    entry["regular_team_stints"] = []
    entry["did_not_play"] = {"regular": True, "postseason": False}

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is True
    assert _issue_codes(report) == set()


@pytest.mark.unit
def test_validate_official_stats_coverage_passes_regular_roster_presence_with_did_not_play(
    session: Session,
) -> None:
    """Did-not-play evidence suppresses only the aggregate expectation: a
    player can be marked `did_not_play.regular` and still have real
    roster/team-stint rows from the team page, and that must pass too.
    """

    _insert_clean_dataset(session)
    _delete_regular_aggregate_rows(session, player_season_id=2)

    artifact = _coverage_artifact_for_clean_dataset()
    entry = _find_coverage_entry(artifact, "hardeja01", 2021)
    entry["regular_aggregate_tables"] = []
    entry["did_not_play"] = {"regular": True, "postseason": False}
    # entry["regular_team_stints"] is left untouched: the roster/team-stint
    # rows in the DB are untouched too, so they must still match.

    report = validate_official_stats(session, coverage_artifact=artifact)

    assert report.passed is True
    assert _issue_codes(report) == set()


@pytest.mark.unit
def test_cli_validate_official_stats_passes_coverage_artifact_and_cache_root_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coverage_artifact_path = tmp_path / "coverage.json"
    coverage_artifact_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    cache_root = tmp_path / "cache"
    cache_root.mkdir()

    events: list[str] = []

    class FakeValidationReport:
        passed = True

        def to_dict(self) -> dict[str, object]:
            return {"passed": True}

    class FakeEngine:
        def dispose(self) -> None:
            events.append("engine_dispose")

    class FakeSession:
        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    fake_engine = FakeEngine()
    fake_session = FakeSession()

    def fake_validate(
        session: object,
        backfill_data: object,
        *,
        coverage_artifact: object,
        coverage_cache_root: object,
    ) -> FakeValidationReport:
        assert session is fake_session
        assert coverage_artifact == {"schema_version": 1}
        assert coverage_cache_root == cache_root
        events.append("validate")
        return FakeValidationReport()

    monkeypatch.setattr("nba_data.cli.main.create_db_engine", lambda settings: fake_engine)
    monkeypatch.setattr(
        "nba_data.cli.main.create_session_factory", lambda engine: (lambda: fake_session)
    )
    monkeypatch.setattr("nba_data.cli.main.run_official_stats_validation", fake_validate)

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "official-stats",
            "--coverage-artifact",
            str(coverage_artifact_path),
            "--coverage-cache-root",
            str(cache_root),
        ],
    )

    assert result.exit_code == 0
    assert events == ["validate", "engine_dispose"]


def _find_coverage_entry(artifact: dict[str, object], player_id: str, season_year: int) -> dict[str, object]:
    return next(
        entry
        for entry in artifact["entries"]  # type: ignore[index]
        if entry["basketball_reference_player_id"] == player_id and entry["season_year"] == season_year
    )


def _fake_aggregate_entry(
    player_id: str, season_year: int, table: str, *, postseason: bool = False
) -> dict[str, object]:
    return {
        "basketball_reference_player_id": player_id,
        "season_year": season_year,
        "regular_aggregate_tables": [] if postseason else [table],
        "postseason_aggregate_tables": [table] if postseason else [],
        "regular_team_stints": [],
        "postseason_team_stints": [],
        "did_not_play": {"regular": False, "postseason": False},
    }


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


# The `core.player_seasons` / `core.player_team_seasons` identity `_insert_clean_dataset`
# builds, keyed by the same grain values `_grains_for_spec` returns. Used to derive a
# stats-coverage artifact that expects exactly the rows the fixture inserts, so the two
# cannot silently drift out of sync.
_CLEAN_PLAYER_SEASON_GRAINS = {
    1: ("brownja02", 2024),
    2: ("hardeja01", 2021),
}
_CLEAN_PLAYER_TEAM_SEASON_GRAINS = {
    1: ("brownja02", 2024, "BOS"),
    2: ("hardeja01", 2021, "HOU"),
    3: ("hardeja01", 2021, "BRK"),
}


def _coverage_artifact_for_clean_dataset() -> dict[str, object]:
    """A stats-coverage artifact (F4E-017 shape) matching `_insert_clean_dataset`.

    Derived from `STATS_TABLE_SPECS` and the same grain identity maps the fixture
    inserts against, rather than a hand-written key list, so a change to the
    fixture or the table specs cannot silently desync from what this expects.
    """

    entries: dict[tuple[str, int], dict[str, set[object]]] = {}

    def entry_for(player_id: str, season_year: int) -> dict[str, set[object]]:
        return entries.setdefault(
            (player_id, season_year),
            {
                "regular_aggregate_tables": set(),
                "postseason_aggregate_tables": set(),
                "regular_team_stints": set(),
                "postseason_team_stints": set(),
            },
        )

    for grain in _grains_for_spec(REGULAR_AGGREGATE_TABLE_SPECS[0]):
        player_id, season_year = _CLEAN_PLAYER_SEASON_GRAINS[grain]
        entry_for(player_id, season_year)["regular_aggregate_tables"].update(
            spec.full_name for spec in REGULAR_AGGREGATE_TABLE_SPECS
        )
    for grain in _grains_for_spec(POSTSEASON_AGGREGATE_TABLE_SPECS[0]):
        player_id, season_year = _CLEAN_PLAYER_SEASON_GRAINS[grain]
        entry_for(player_id, season_year)["postseason_aggregate_tables"].update(
            spec.full_name for spec in POSTSEASON_AGGREGATE_TABLE_SPECS
        )
    for grain in _grains_for_spec(REGULAR_TEAM_STINT_TABLE_SPECS[0]):
        player_id, season_year, team_code = _CLEAN_PLAYER_TEAM_SEASON_GRAINS[grain]
        entry_for(player_id, season_year)["regular_team_stints"].update(
            (team_code, spec.full_name) for spec in REGULAR_TEAM_STINT_TABLE_SPECS
        )
    for grain in _grains_for_spec(POSTSEASON_TEAM_STINT_TABLE_SPECS[0]):
        player_id, season_year, team_code = _CLEAN_PLAYER_TEAM_SEASON_GRAINS[grain]
        entry_for(player_id, season_year)["postseason_team_stints"].update(
            (team_code, spec.full_name) for spec in POSTSEASON_TEAM_STINT_TABLE_SPECS
        )

    serialized_entries = [
        {
            "basketball_reference_player_id": player_id,
            "season_year": season_year,
            "regular_aggregate_tables": sorted(entry["regular_aggregate_tables"]),
            "postseason_aggregate_tables": sorted(entry["postseason_aggregate_tables"]),
            "regular_team_stints": [
                {"team_code": team_code, "table": table}
                for team_code, table in sorted(entry["regular_team_stints"])
            ],
            "postseason_team_stints": [
                {"team_code": team_code, "table": table}
                for team_code, table in sorted(entry["postseason_team_stints"])
            ],
            "did_not_play": {"regular": False, "postseason": False},
        }
        for (player_id, season_year), entry in sorted(entries.items())
    ]

    return {
        "schema_version": 1,
        "cache_root": "/fake/cache",
        "parser_contracts": {},
        "cache_fingerprint": {"digest": "0" * 64, "player_page_count": 0, "team_page_count": 0},
        "counts": {},
        "entries": serialized_entries,
        "unexplained": [],
        "disagreements": [],
        "source_issues": [],
    }


def _stats_row_params(spec, grain: int) -> dict[str, object]:
    if spec.season_type == "postseason":
        base = {
            "source_url": "https://example.test/players/sample.html#playoffs",
            "cache_path": "cache/player_postseason.html.gz",
            "parser_version": current_parser_version("player_page_postseason"),
        }
    elif spec.family == "aggregate":
        base = {
            "source_url": "https://example.test/players/sample.html",
            "cache_path": "cache/player_regular.html.gz",
            "parser_version": current_parser_version("player_page_regular"),
        }
    else:
        base = {
            "source_url": "https://example.test/teams/sample/2024.html",
            "cache_path": "cache/team_regular.html.gz",
            "parser_version": current_parser_version("team_season"),
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


def _stats_backfill_reports(
    *,
    team_rows: int = 30,
    player_rows: int = 25,
    postseason_aggregate_rows: int = 10,
    postseason_team_rows: int = 10,
) -> dict[str, dict[str, object]]:
    return {
        "team_stats": _team_stats_report(stats_loaded_rows=team_rows),
        "player_stats": _player_stats_report(rows_loaded_or_updated=player_rows),
        "player_postseason_stats": _postseason_stats_report(
            aggregate_rows_loaded_or_updated=postseason_aggregate_rows,
            team_rows_loaded_or_updated=postseason_team_rows,
        ),
    }


def _team_stats_report(*, stats_loaded_rows: int) -> dict[str, object]:
    return {
        "selected_sources": 5,
        "processed_sources": 5,
        "processing_failed_sources": 0,
        "entries_failed": 0,
        "rows_failed": 0,
        "stats_loaded_rows": stats_loaded_rows,
        "stats_skipped_rows": 0,
        "stats_failed_rows": 0,
        "stats_quarantined_rows": 0,
    }


def _player_stats_report(*, rows_loaded_or_updated: int) -> dict[str, object]:
    return {
        "player_pages_processed": 1,
        "rows_loaded_or_updated": rows_loaded_or_updated,
        "entries_failed": 0,
        "rows_failed": 0,
        "unresolved_players_or_seasons": 0,
        "cache_root": str(Path.cwd()),
        "discovery_status": "ok",
    }


def _postseason_stats_report(
    *,
    aggregate_rows_loaded_or_updated: int,
    team_rows_loaded_or_updated: int,
) -> dict[str, object]:
    return {
        "player_pages_processed": 1,
        "aggregate_rows_loaded_or_updated": aggregate_rows_loaded_or_updated,
        "team_rows_loaded_or_updated": team_rows_loaded_or_updated,
        "entries_failed": 0,
        "rows_failed": 0,
        "unresolved_players_or_seasons_or_team_stints": 0,
        "cache_root": str(Path.cwd()),
        "discovery_status": "ok",
    }


def _issue_codes(report) -> set[str]:
    return {issue.code for issue in report.issues}
