from __future__ import annotations

import inspect

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import nba_data.scraping.offline_reporting as offline_reporting
from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.scraping.offline_loader import load_offline_team_season_report
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonProcessingReport,
    OfflineTeamSeasonSourceContext,
)
from nba_data.scraping.offline_reporting import build_offline_team_season_audit_report
from nba_data.validation.team_season import DataQualityIssue

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
def session() -> Session:
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
def test_audit_report_distinguishes_processing_loading_and_quarantine_rows(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_loader(session: Session, batch: object) -> object:
        raise RuntimeError("database rejected validated rows")

    monkeypatch.setattr("nba_data.scraping.offline_loader.load_team_season_core", fail_loader)
    processing_report = _processing_report(
        [
            _validated_entry(rows=[_row(), _row(source_table="roster")]),
            _validation_failed_entry(rows=[_row(basketball_reference_player_id=None)]),
        ]
    )
    load_report = load_offline_team_season_report(session, processing_report)

    audit_report = build_offline_team_season_audit_report(processing_report, load_report)

    assert audit_report.parsed_rows == 3
    assert audit_report.validated_rows == 2
    assert audit_report.loaded_rows == 0
    assert audit_report.skipped_rows == 0
    assert audit_report.quarantined_rows == 3
    assert audit_report.loaded_entries == 0
    assert audit_report.skipped_entries == 1
    assert audit_report.failed_entries == 1
    assert [entry.reason for entry in audit_report.quarantine_entries] == [
        "validation_failed",
        "loading_failed",
    ]
    assert audit_report.quarantine_entries[0].team_abbreviation == "BOS"
    assert audit_report.quarantine_entries[0].cache_path == "cache/bos.html.gz"
    assert audit_report.quarantine_entries[0].validation_issues[0].code == "missing_player_id"
    assert "rerun the offline processor" in audit_report.quarantine_entries[0].retry_hint
    assert "idempotent loader path" in audit_report.quarantine_entries[1].retry_hint


@pytest.mark.unit
def test_successful_rerun_report_stays_retry_safe(session: Session) -> None:
    processing_report = _processing_report(
        [_validated_entry(rows=[_row(), _row(source_table="roster")])]
    )

    first = load_offline_team_season_report(session, processing_report)
    second = load_offline_team_season_report(session, processing_report)

    first_audit = build_offline_team_season_audit_report(processing_report, first)
    second_audit = build_offline_team_season_audit_report(processing_report, second)

    assert first_audit.loaded_rows == 2
    assert second_audit.loaded_rows == 2
    assert first_audit.quarantined_rows == 0
    assert second_audit.quarantined_rows == 0
    assert first_audit.to_dict()["loaded_rows"] == second_audit.to_dict()["loaded_rows"]


@pytest.mark.unit
def test_processing_failures_keep_source_context_for_retry_without_loading() -> None:
    processing_report = _processing_report(
        [_processing_failed_entry(error_message="Cached HTML file not found")]
    )

    audit_report = build_offline_team_season_audit_report(processing_report)

    assert audit_report.parsed_rows == 0
    assert audit_report.validated_rows == 0
    assert audit_report.loaded_rows == 0
    assert audit_report.quarantined_entries == 1
    assert audit_report.quarantined_rows == 0
    quarantine = audit_report.quarantine_entries[0]
    assert quarantine.reason == "processing_failed"
    assert quarantine.source_url == "https://www.basketball-reference.com/teams/BOS/2024.html"
    assert quarantine.team_abbreviation == "BOS"
    assert quarantine.season_year == 2024
    assert "Cached HTML file not found" in str(quarantine.error_message)


@pytest.mark.unit
def test_offline_reporting_does_not_accept_or_import_network_boundaries() -> None:
    signature = inspect.signature(build_offline_team_season_audit_report)
    module_source = inspect.getsource(offline_reporting)

    assert "client" not in signature.parameters
    assert "BasketballReferenceClient" not in module_source
    assert "import requests" not in module_source
    assert "import httpx" not in module_source


def _processing_report(
    entries: list[OfflineTeamSeasonEntryResult],
) -> OfflineTeamSeasonProcessingReport:
    return OfflineTeamSeasonProcessingReport(
        total_inputs=len(entries),
        validated_entries=sum(entry.status == "validated" for entry in entries),
        failed_entries=sum(entry.status == "failed" for entry in entries),
        validated_row_count=sum(len(entry.normalized_rows) for entry in entries),
        entries=tuple(entries),
    )


def _validated_entry(
    *,
    rows: list[dict[str, object]] | None = None,
) -> OfflineTeamSeasonEntryResult:
    normalized_rows = tuple(rows or [_row()])
    return OfflineTeamSeasonEntryResult(
        source=_source_context(),
        status="validated",
        parsed_row_count=len(normalized_rows),
        normalized_rows=normalized_rows,
    )


def _validation_failed_entry(
    *,
    rows: list[dict[str, object]],
) -> OfflineTeamSeasonEntryResult:
    quarantined_rows = tuple(rows)
    return OfflineTeamSeasonEntryResult(
        source=_source_context(),
        status="failed",
        parsed_row_count=len(quarantined_rows),
        quarantined_rows=quarantined_rows,
        validation_issues=(
            DataQualityIssue(
                code="missing_player_id",
                message="Missing Basketball Reference player ID.",
                row_index=0,
                source_table="totals",
            ),
        ),
        error_message="Validation failed for cached team-season HTML with 1 issue(s).",
    )


def _processing_failed_entry(*, error_message: str) -> OfflineTeamSeasonEntryResult:
    return OfflineTeamSeasonEntryResult(
        source=_source_context(),
        status="failed",
        error_message=error_message,
    )


def _source_context() -> OfflineTeamSeasonSourceContext:
    return OfflineTeamSeasonSourceContext(
        source_type="url",
        team_abbreviation="BOS",
        season_year=2024,
        url="https://www.basketball-reference.com/teams/BOS/2024.html",
        cache_path="cache/bos.html.gz",
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
