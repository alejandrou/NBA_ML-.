from __future__ import annotations

import inspect
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import nba_data.cli.main as cli_main
import nba_data.scraping.offline_stats_backfill as offline_stats_backfill
from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerSeasonAdjShooting,
    PlayerSeasonAdvanced,
    PlayerSeasonPbp,
    PlayerSeasonPerGame,
    PlayerSeasonPerMinute,
    PlayerSeasonPerPoss,
    PlayerSeasonShooting,
    PlayerSeasonTotals,
    PlayerTeamSeason,
    PlayerTeamSeasonAdjShooting,
    PlayerTeamSeasonAdvanced,
    PlayerTeamSeasonPbp,
    PlayerTeamSeasonPerGame,
    PlayerTeamSeasonPerMinute,
    PlayerTeamSeasonPerPoss,
    PlayerTeamSeasonRoster,
    PlayerTeamSeasonShooting,
    PlayerTeamSeasonTotals,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import CachedHtmlInventory, CachedHtmlInventoryEntry
from nba_data.scraping.loaders import TeamSeasonStatsLoadEntry, TeamSeasonStatsLoadReport
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonProcessingReport,
    OfflineTeamSeasonSourceContext,
)
from nba_data.scraping.offline_stats_backfill import run_offline_stats_backfill

BOS_2024_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
BOS_2025_URL = "https://www.basketball-reference.com/teams/BOS/2025.html"
ATL_2024_URL = "https://www.basketball-reference.com/teams/ATL/2024.html"
DEN_2023_URL = "https://www.basketball-reference.com/teams/DEN/2023.html"

CORE_TABLES = (
    Season.__table__,
    Team.__table__,
    TeamAlias.__table__,
    Player.__table__,
    TeamSeason.__table__,
    PlayerSeason.__table__,
    PlayerTeamSeason.__table__,
)

STATS_TABLES = (
    PlayerTeamSeasonRoster.__table__,
    PlayerTeamSeasonTotals.__table__,
    PlayerTeamSeasonPerGame.__table__,
    PlayerTeamSeasonPerMinute.__table__,
    PlayerTeamSeasonPerPoss.__table__,
    PlayerTeamSeasonAdvanced.__table__,
    PlayerTeamSeasonShooting.__table__,
    PlayerTeamSeasonAdjShooting.__table__,
    PlayerTeamSeasonPbp.__table__,
    PlayerSeasonTotals.__table__,
    PlayerSeasonPerGame.__table__,
    PlayerSeasonPerMinute.__table__,
    PlayerSeasonPerPoss.__table__,
    PlayerSeasonAdvanced.__table__,
    PlayerSeasonShooting.__table__,
    PlayerSeasonAdjShooting.__table__,
    PlayerSeasonPbp.__table__,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for table in (*CORE_TABLES, *STATS_TABLES):
            table.create(connection)

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as test_session:
        yield test_session

    engine.dispose()


@pytest.mark.unit
def test_stats_backfill_uses_only_valid_inventory_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    valid_path = cache.path_for_url(BOS_2024_URL)
    inventory = _inventory(
        cache.root_dir,
        [
            _entry(valid_path, "valid", team="BOS", season=2024),
            _entry(cache.path_for_url(BOS_2025_URL), "duplicate", team="BOS", season=2025),
            _entry(cache.path_for_url(DEN_2023_URL), "invalid_or_unreadable", team="DEN", season=2023),
        ],
    )
    captured_sources: list[object] = []

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        captured_sources.extend(tuple(sources))
        return _processing_report([_failed_entry(cache_path=str(valid_path))])

    def fail_loader(*args: object, **kwargs: object) -> object:
        raise AssertionError("processing failures must not call the stats loader")

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)
    monkeypatch.setattr(offline_stats_backfill, "load_team_season_stats", fail_loader)

    report = run_offline_stats_backfill(_FakeSession(), cache=cache)

    assert len(captured_sources) == 1
    assert report.valid_inventory_entries == 1
    assert report.selected_sources == 1
    assert report.processed_sources == 1
    assert report.processing_failed_sources == 1
    assert captured_sources[0].path == valid_path  # type: ignore[attr-defined]


@pytest.mark.unit
def test_stats_backfill_filters_and_sorts_deterministically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [
            _entry(cache.path_for_url(BOS_2025_URL), "valid", team="BOS", season=2025),
            _entry(cache.path_for_url(DEN_2023_URL), "valid", team="DEN", season=2023),
            _entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2024),
            _entry(cache.path_for_url(ATL_2024_URL), "valid", team="ATL", season=2024),
        ],
    )
    captured_batches: list[tuple[tuple[str, int], ...]] = []

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        source_tuple = tuple(sources)
        captured_batches.append(
            tuple((source.team_abbreviation, source.season_year) for source in source_tuple)
        )
        return _processing_report(
            [_failed_entry(team=source.team_abbreviation, season=source.season_year) for source in source_tuple]
        )

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)

    run_offline_stats_backfill(
        _FakeSession(),
        cache=cache,
        start_year=2024,
        end_year=2025,
        limit=3,
    )
    run_offline_stats_backfill(
        _FakeSession(),
        cache=cache,
        team="bos",
        start_year=2024,
        end_year=2025,
    )

    assert captured_batches[0] == (("ATL", 2024), ("BOS", 2024), ("BOS", 2025))
    assert captured_batches[1] == (("BOS", 2024), ("BOS", 2025))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"limit": 0}, "limit"),
        ({"max_workers": 0}, "max_workers"),
        ({"team": "TOT"}, "TOT"),
        ({"start_year": 2025, "end_year": 2024}, "start_year"),
        ({"parser_version": " "}, "parser_version"),
    ),
)
def test_stats_backfill_rejects_invalid_arguments(
    tmp_path: Path,
    kwargs: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        run_offline_stats_backfill(_FakeSession(), cache=HtmlCache(tmp_path / "cache"), **kwargs)


@pytest.mark.unit
def test_stats_backfill_calls_processor_with_max_workers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [_entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2024)],
    )
    captured_kwargs: dict[str, object] = {}

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        captured_kwargs.update(kwargs)
        return _processing_report([_failed_entry()])

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)

    report = run_offline_stats_backfill(_FakeSession(), cache=cache, max_workers=4)

    assert report.processed_sources == 1
    assert captured_kwargs["cache"] is cache
    assert captured_kwargs["max_workers"] == 4
    assert "client" not in inspect.signature(run_offline_stats_backfill).parameters


@pytest.mark.unit
def test_stats_backfill_calls_stats_loader_for_validated_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    cache_path = cache.path_for_url(BOS_2024_URL)
    inventory = _inventory(cache.root_dir, [_entry(cache_path, "valid", team="BOS", season=2024)])
    fake_session = _FakeSession()
    captured: dict[str, object] = {}
    rows = [_row()]

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        return _processing_report([_validated_entry(rows=rows, cache_path=str(cache_path))])

    def fake_loader(
        session: object,
        loader_rows: object,
        *,
        source_url: str,
        cache_path: str,
        parser_version: str,
    ) -> TeamSeasonStatsLoadReport:
        captured.update(
            {
                "session": session,
                "rows": tuple(loader_rows),
                "source_url": source_url,
                "cache_path": cache_path,
                "parser_version": parser_version,
            }
        )
        return _stats_report(loaded=1)

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)
    monkeypatch.setattr(offline_stats_backfill, "load_team_season_stats", fake_loader)

    report = run_offline_stats_backfill(
        fake_session,
        cache=cache,
        parser_version="parser-test",
    )

    assert report.stats_loaded_rows == 1
    assert fake_session.nested_count == 1
    assert captured == {
        "session": fake_session,
        "rows": tuple(rows),
        "source_url": BOS_2024_URL,
        "cache_path": str(cache_path),
        "parser_version": "parser-test",
    }


@pytest.mark.unit
def test_stats_backfill_does_not_call_stats_loader_for_processing_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [_entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2024)],
    )

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        return _processing_report(
            [_failed_entry(error_message="Validation failed before stats loading.")]
        )

    def fail_loader(*args: object, **kwargs: object) -> object:
        raise AssertionError("processor failures must not load stats")

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)
    monkeypatch.setattr(offline_stats_backfill, "load_team_season_stats", fail_loader)

    report = run_offline_stats_backfill(_FakeSession(), cache=cache)

    assert report.stats_loaded_rows == 0
    assert report.processing_failed_sources == 1
    assert report.entries[0].status == "failed"
    assert "Validation failed" in str(report.entries[0].reason)


@pytest.mark.unit
def test_stats_backfill_aggregates_counts_and_is_json_serializable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    entries = [
        _entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2024),
        _entry(cache.path_for_url(BOS_2025_URL), "valid", team="BOS", season=2025),
        _entry(cache.path_for_url(DEN_2023_URL), "valid", team="DEN", season=2023),
    ]
    inventory = _inventory(cache.root_dir, entries)
    load_reports = iter([_stats_report(loaded=2, skipped=1), _stats_report(failed=3)])

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        return _processing_report(
            [
                _validated_entry(team="DEN", season=2023),
                _validated_entry(team="BOS", season=2024),
                _failed_entry(team="BOS", season=2025, quarantined_rows=[_row(season_year=2025)]),
            ]
        )

    def fake_loader(*args: object, **kwargs: object) -> TeamSeasonStatsLoadReport:
        return next(load_reports)

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)
    monkeypatch.setattr(offline_stats_backfill, "load_team_season_stats", fake_loader)

    report = run_offline_stats_backfill(_FakeSession(), cache=cache)
    payload = report.to_dict()

    assert report.stats_loaded_rows == 2
    assert report.stats_skipped_rows == 1
    assert report.stats_failed_rows == 3
    assert report.stats_quarantined_rows == 4
    assert report.processing_failed_sources == 1
    assert [entry.status for entry in report.entries] == ["loaded", "failed", "failed"]
    assert payload["entries"][0]["loaded_rows"] == 2  # type: ignore[index]
    json.dumps(payload)


@pytest.mark.unit
def test_cli_backfill_stats_refuses_without_explicit_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "stats-report.json"

    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("CLI guard must fail before database engine creation")

    monkeypatch.setattr(cli_main, "create_db_engine", fail_engine)

    result = CliRunner().invoke(app, ["backfill", "stats", "--output", str(output_path)])

    assert result.exit_code != 0
    assert "Refusing stats backfill" in result.output
    assert not output_path.exists()


@pytest.mark.unit
def test_cli_backfill_stats_runs_with_fake_session_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    output_path = tmp_path / "reports" / "stats-backfill.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()

    class FakeReport:
        def to_dict(self) -> dict[str, object]:
            return {"selected_sources": 1, "stats_loaded_rows": 2}

    class FakeEngine:
        def dispose(self) -> None:
            events.append("engine_dispose")

    class FakeTransaction:
        def __enter__(self) -> FakeTransaction:
            events.append("transaction_enter")
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            events.append("transaction_exit")

    class FakeSession:
        def __enter__(self) -> FakeSession:
            events.append("session_enter")
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            events.append("session_exit")

        def begin(self) -> FakeTransaction:
            events.append("session_begin")
            return FakeTransaction()

    fake_engine = FakeEngine()
    fake_session = FakeSession()

    def fake_engine_factory(settings: object) -> FakeEngine:
        events.append("engine_create")
        return fake_engine

    def fake_session_factory(engine: object) -> object:
        assert engine is fake_engine
        events.append("session_factory_create")
        return lambda: fake_session

    def fake_backfill(
        session: object,
        *,
        cache: HtmlCache,
        max_workers: int,
        limit: int | None,
        team: str | None,
        start_year: int | None,
        end_year: int | None,
        parser_version: str,
    ) -> FakeReport:
        assert session is fake_session
        assert cache.root_dir == tmp_path / "cache"
        assert max_workers == 2
        assert limit == 5
        assert team == "bos"
        assert start_year == 2024
        assert end_year == 2025
        assert parser_version == "parser-test"
        events.append("stats_backfill_run")
        return FakeReport()

    monkeypatch.setattr(cli_main, "create_db_engine", fake_engine_factory)
    monkeypatch.setattr(cli_main, "create_session_factory", fake_session_factory)
    monkeypatch.setattr(cli_main, "run_offline_stats_backfill", fake_backfill)

    result = CliRunner().invoke(
        app,
        [
            "backfill",
            "stats",
            "--execute-approved-stats-backfill",
            "--max-workers",
            "2",
            "--limit",
            "5",
            "--team",
            "bos",
            "--start-year",
            "2024",
            "--end-year",
            "2025",
            "--parser-version",
            "parser-test",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert events == [
        "engine_create",
        "session_factory_create",
        "session_enter",
        "session_begin",
        "transaction_enter",
        "stats_backfill_run",
        "transaction_exit",
        "session_exit",
        "engine_dispose",
    ]
    assert json.loads(result.output) == {"selected_sources": 1, "stats_loaded_rows": 2}
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "selected_sources": 1,
        "stats_loaded_rows": 2,
    }


@pytest.mark.unit
def test_stats_backfill_source_has_no_network_core_loader_or_commit_boundaries() -> None:
    module_source = inspect.getsource(offline_stats_backfill)
    command_source = inspect.getsource(cli_main.backfill_stats)

    for source in (module_source, command_source):
        for forbidden in (
            "BasketballReferenceClient",
            "import requests",
            "import httpx",
            "acquisition",
            "HtmlCache.set",
            "load_offline_team_season_report",
            "load_team_season_core",
            ".commit(",
            ".rollback(",
        ):
            assert forbidden not in source


@pytest.mark.unit
def test_source_level_savepoint_rolls_back_failed_source_and_continues(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [
            _entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2024),
            _entry(cache.path_for_url(BOS_2025_URL), "valid", team="BOS", season=2025),
        ],
    )

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        return _processing_report(
            [
                _validated_entry(season=2024, rows=[_row(season_year=2024)]),
                _validated_entry(season=2025, rows=[_row(season_year=2025)]),
            ]
        )

    def fake_loader(
        session: Session,
        rows: object,
        **kwargs: object,
    ) -> TeamSeasonStatsLoadReport:
        row_tuple = tuple(rows)
        if row_tuple[0]["season_year"] == 2024:
            session.add(Season(league="NBA", season_year=2098, label="2098"))
            session.flush()
            raise RuntimeError("simulated stats loader failure")
        return _stats_report(loaded=1)

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)
    monkeypatch.setattr(offline_stats_backfill, "load_team_season_stats", fake_loader)

    report = run_offline_stats_backfill(session, cache=cache)

    assert [entry.status for entry in report.entries] == ["failed", "loaded"]
    assert report.stats_loaded_rows == 1
    assert report.stats_failed_rows == 1
    assert _count(session, Season) == 0


@pytest.mark.unit
def test_stats_backfill_rerun_is_idempotent_with_existing_loader(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_core_grains(session)
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [_entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2024)],
    )

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        return _processing_report([_validated_entry(rows=[_row()])])

    monkeypatch.setattr(offline_stats_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_stats_backfill, "process_offline_team_season_sources", fake_process)

    first = run_offline_stats_backfill(session, cache=cache)
    second = run_offline_stats_backfill(session, cache=cache)

    assert first.stats_loaded_rows == 1
    assert second.stats_loaded_rows == 1
    assert _count(session, PlayerTeamSeasonTotals) == 1


class _FakeTransaction:
    def __enter__(self) -> _FakeTransaction:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


class _FakeSession:
    def __init__(self) -> None:
        self.nested_count = 0

    def begin_nested(self) -> _FakeTransaction:
        self.nested_count += 1
        return _FakeTransaction()


def _inventory(
    cache_root: Path,
    entries: list[CachedHtmlInventoryEntry],
) -> CachedHtmlInventory:
    return CachedHtmlInventory(
        cache_root=str(cache_root.resolve(strict=False)),
        total_discovered_files=len(entries),
        valid_candidates=sum(entry.status == "valid" for entry in entries),
        invalid_or_unreadable_files=sum(
            entry.status == "invalid_or_unreadable" for entry in entries
        ),
        duplicate_candidates=sum(entry.status == "duplicate" for entry in entries),
        missing_metadata=sum(entry.status == "missing_metadata" for entry in entries),
        unsupported_paths=sum(entry.status == "unsupported_path" for entry in entries),
        entries=tuple(entries),
    )


def _entry(
    path: Path,
    status: str,
    *,
    team: str | None = None,
    season: int | None = None,
) -> CachedHtmlInventoryEntry:
    return CachedHtmlInventoryEntry(
        cache_path=str(path),
        status=status,
        source_url=(
            f"https://www.basketball-reference.com/teams/{team}/{season}.html"
            if team is not None and season is not None
            else None
        ),
        is_basketball_reference="basketball-reference" in path.parts,
        team_abbreviation=team,
        season_year=season,
        season_end_year=season,
        page_type="team_season" if team is not None and season is not None else None,
    )


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
    team: str = "BOS",
    season: int = 2024,
    source_url: str | None = None,
    cache_path: str | None = "cache/bos.html.gz",
    rows: list[dict[str, object]] | None = None,
) -> OfflineTeamSeasonEntryResult:
    normalized_rows = tuple(rows or [_row(season_year=season, team_abbreviation=team)])
    return OfflineTeamSeasonEntryResult(
        source=OfflineTeamSeasonSourceContext(
            source_type="path",
            team_abbreviation=team,
            season_year=season,
            url=source_url,
            cache_path=cache_path,
        ),
        status="validated",
        parsed_row_count=len(normalized_rows),
        normalized_rows=normalized_rows,
    )


def _failed_entry(
    *,
    team: str = "BOS",
    season: int = 2024,
    cache_path: str | None = "cache/bos.html.gz",
    error_message: str = "Offline processing failed.",
    quarantined_rows: list[dict[str, object]] | None = None,
) -> OfflineTeamSeasonEntryResult:
    return OfflineTeamSeasonEntryResult(
        source=OfflineTeamSeasonSourceContext(
            source_type="path",
            team_abbreviation=team,
            season_year=season,
            cache_path=cache_path,
        ),
        status="failed",
        quarantined_rows=tuple(quarantined_rows or []),
        error_message=error_message,
    )


def _stats_report(
    *,
    loaded: int = 0,
    skipped: int = 0,
    failed: int = 0,
) -> TeamSeasonStatsLoadReport:
    entries = []
    for index in range(loaded):
        entries.append(_stats_entry(index, status="loaded", reason="loaded"))
    for index in range(loaded, loaded + skipped):
        entries.append(_stats_entry(index, status="skipped", reason="missing_core"))
    for index in range(loaded + skipped, loaded + skipped + failed):
        entries.append(_stats_entry(index, status="failed", reason="repository_error"))
    return TeamSeasonStatsLoadReport(
        total_rows=loaded + skipped + failed,
        loaded_rows=loaded,
        skipped_rows=skipped,
        failed_rows=failed,
        entries=tuple(entries),
    )


def _stats_entry(
    row_index: int,
    *,
    status: str,
    reason: str,
) -> TeamSeasonStatsLoadEntry:
    return TeamSeasonStatsLoadEntry(
        row_index=row_index,
        status=status,
        reason=reason,
        source_table="totals",
        stat_scope="player_team_season",
        team_abbreviation="BOS",
        player_identifier="tatumja01",
        destination_table="stats.player_team_season_totals",
    )


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "league": "NBA",
        "season_year": 2024,
        "team_abbreviation": "BOS",
        "team_context": "team",
        "source_table": "totals",
        "stat_scope": "player_team_season",
        "player_name": "Jayson Tatum",
        "basketball_reference_player_id": "tatumja01",
        "stable_player_key": "tatumja01",
        "identifier_status": "present",
        "values": {"games": 74, "pts": 1987},
    }
    row.update(overrides)
    return row


def _create_core_grains(session: Session) -> tuple[PlayerTeamSeason, PlayerSeason]:
    repository = CoreRepository(session)
    season = repository.get_or_create_season(league="NBA", season_year=2024)
    team = repository.get_or_create_team(
        basketball_reference_team_id="BOS",
        current_abbreviation="BOS",
        current_name="Boston Celtics",
    )
    repository.get_or_create_team_alias(
        team=team,
        abbreviation="BOS",
        name="Boston Celtics",
        season_year=2024,
    )
    team_season = repository.get_or_create_team_season(
        team=team,
        season=season,
        team_abbreviation="BOS",
    )
    player = repository.get_or_create_player(
        basketball_reference_player_id="tatumja01",
        full_name="Jayson Tatum",
    )
    player_season = repository.get_or_create_player_season(player=player, season=season)
    player_team_season = repository.get_or_create_player_team_season(
        player_season=player_season,
        team_season=team_season,
        roster_number="0",
        roster_position="SF",
    )
    return player_team_season, player_season


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
