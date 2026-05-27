from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import nba_data.scraping.offline_loader as offline_loader
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
def test_validated_offline_report_rerun_creates_no_duplicate_core_rows(
    session: Session,
) -> None:
    processing_report = _processing_report(
        [
            _validated_entry(
                rows=[_row(), _row(source_table="roster"), _aggregate_row()],
            )
        ]
    )

    first = load_offline_team_season_report(session, processing_report)
    second = load_offline_team_season_report(session, processing_report)

    assert first.loaded_entries == 1
    assert second.loaded_entries == 1
    assert second.loaded_rows == 3
    assert _count(session, Season) == 1
    assert _count(session, Team) == 1
    assert _count(session, TeamAlias) == 1
    assert _count(session, TeamSeason) == 1
    assert _count(session, Player) == 2
    assert _count(session, PlayerSeason) == 2
    assert _count(session, PlayerTeamSeason) == 1


@pytest.mark.unit
def test_processor_failure_entries_do_not_call_db_loader(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_loader(*args: object, **kwargs: object) -> object:
        raise AssertionError("processor failures must not call DB loaders")

    monkeypatch.setattr(offline_loader, "load_team_season_core", fail_loader)
    processing_report = _processing_report(
        [_failed_entry(error_message="Validation failed before loading.")]
    )

    load_report = load_offline_team_season_report(session, processing_report)

    assert load_report.loaded_entries == 0
    assert load_report.skipped_entries == 1
    assert load_report.failed_entries == 0
    assert load_report.entries[0].status == "skipped"
    assert load_report.entries[0].error_message == "Validation failed before loading."
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
def test_loader_failure_rolls_back_partial_entry_writes(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_after_write(session: Session, batch: object) -> object:
        session.add(Season(league="NBA", season_year=2098, label="2098"))
        session.flush()
        raise RuntimeError("simulated loader failure")

    monkeypatch.setattr(offline_loader, "load_team_season_core", fail_after_write)
    processing_report = _processing_report(
        [_validated_entry(season_year=2098, rows=[_row(season_year=2098)])]
    )

    load_report = load_offline_team_season_report(session, processing_report)

    assert load_report.loaded_entries == 0
    assert load_report.failed_entries == 1
    assert "simulated loader failure" in str(load_report.entries[0].error_message)
    assert _count(session, Season) == 0


@pytest.mark.unit
def test_source_context_is_preserved_at_result_level(session: Session) -> None:
    source_url = "https://www.basketball-reference.com/teams/BOS/2024.html"
    cache_path = "data/raw/html/basketball-reference/bos.html.gz"
    processing_report = _processing_report(
        [
            _validated_entry(
                source_url=source_url,
                cache_path=cache_path,
                team_abbreviation="BOS",
                season_year=2024,
            )
        ]
    )

    load_report = load_offline_team_season_report(session, processing_report)

    entry = load_report.entries[0]
    assert entry.status == "loaded"
    assert entry.source_url == source_url
    assert entry.cache_path == cache_path
    assert entry.team_abbreviation == "BOS"
    assert entry.season_year == 2024
    assert entry.to_dict()["source_url"] == source_url


@pytest.mark.unit
def test_offline_loader_does_not_accept_or_import_network_boundaries() -> None:
    signature = inspect.signature(load_offline_team_season_report)
    module_source = inspect.getsource(offline_loader)

    assert "client" not in signature.parameters
    assert "BasketballReferenceClient" not in module_source
    assert "import requests" not in module_source
    assert "import httpx" not in module_source


@pytest.mark.unit
def test_offline_loader_does_not_commit(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_commit() -> None:
        raise AssertionError("offline loader orchestration must not commit")

    monkeypatch.setattr(session, "commit", fail_commit)
    processing_report = _processing_report([_validated_entry()])

    load_report = load_offline_team_season_report(session, processing_report)

    assert load_report.loaded_entries == 1
    assert _count(session, Season) == 1


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
    source_url: str | None = "https://www.basketball-reference.com/teams/BOS/2024.html",
    cache_path: str | None = "cache/bos.html.gz",
    team_abbreviation: str = "BOS",
    season_year: int = 2024,
    rows: list[dict[str, object]] | None = None,
) -> OfflineTeamSeasonEntryResult:
    return OfflineTeamSeasonEntryResult(
        source=OfflineTeamSeasonSourceContext(
            source_type="url" if source_url else "path",
            team_abbreviation=team_abbreviation,
            season_year=season_year,
            url=source_url,
            cache_path=cache_path,
        ),
        status="validated",
        normalized_rows=tuple(rows or [_row()]),
    )


def _failed_entry(
    *,
    error_message: str = "Processor failed.",
) -> OfflineTeamSeasonEntryResult:
    return OfflineTeamSeasonEntryResult(
        source=OfflineTeamSeasonSourceContext(
            source_type="url",
            team_abbreviation="BOS",
            season_year=2024,
            url="https://www.basketball-reference.com/teams/BOS/2024.html",
            cache_path="cache/bos.html.gz",
        ),
        status="failed",
        error_message=error_message,
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
