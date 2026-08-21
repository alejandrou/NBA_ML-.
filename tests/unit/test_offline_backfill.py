from __future__ import annotations

import gzip
import inspect
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import nba_data.scraping.offline_backfill as offline_backfill
from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import CachedHtmlInventory, CachedHtmlInventoryEntry
from nba_data.scraping.offline_backfill import (
    build_offline_team_season_sources_from_inventory,
    run_full_offline_backfill,
)
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonProcessingReport,
    OfflineTeamSeasonSourceContext,
)

BOS_2024_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
DEN_2023_URL = "https://www.basketball-reference.com/teams/DEN/2023.html"
PHASE3_FIXTURE = Path("tests/fixtures/html/team_season_phase3.html")
TEAM_NAME_FIXTURE = Path("tests/fixtures/html/team_season_bos_2000_h1.html")
VALID_HTML = "<!doctype html><html><body>cached</body></html>"

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
def test_full_offline_backfill_loads_valid_inventory_entry_and_reports(
    tmp_path: Path,
    session: Session,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(BOS_2024_URL), PHASE3_FIXTURE.read_text(encoding="utf-8"))

    report = run_full_offline_backfill(cache=cache, session=session)
    data = report.to_dict()

    assert report.inventory.total_discovered_files == 1
    assert report.inventory.valid_candidates == 1
    assert report.selected_inventory_entries == 1
    assert report.skipped_inventory_entries == 0
    assert report.processing_report.validated_entries == 1
    assert report.processing_report.validated_row_count == 9
    assert report.load_report.loaded_entries == 1
    assert report.load_report.loaded_rows == 9
    assert report.audit_report.total_sources == 1
    assert report.audit_report.loaded_rows == 9
    assert report.audit_report.quarantined_entries == 0
    assert data["inventory"]["entries"][0]["source_url"] == BOS_2024_URL
    assert data["load_report"]["loaded_entries"] == 1
    assert data["audit_report"]["loaded_rows"] == 9
    assert _count(session, Season) == 1
    assert _count(session, Team) == 1
    assert _count(session, Player) == 1
    assert _count(session, PlayerSeason) == 1
    assert _count(session, PlayerTeamSeason) == 1


@pytest.mark.unit
def test_full_offline_backfill_hands_derived_name_to_core_loader(
    tmp_path: Path,
    session: Session,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    html = (
        "<!doctype html><html><body>"
        + TEAM_NAME_FIXTURE.read_text(encoding="utf-8")
        + PHASE3_FIXTURE.read_text(encoding="utf-8")
        + "</body></html>"
    )
    _write_gzip(cache.path_for_url(BOS_2024_URL), html)

    report = run_full_offline_backfill(cache=cache, session=session)

    team = session.scalar(select(Team).where(Team.basketball_reference_team_id == "BOS"))
    alias = session.scalar(select(TeamAlias).where(TeamAlias.abbreviation == "BOS"))
    assert report.processing_report.entries[0].team_name == "Boston Celtics"
    assert team is not None
    assert team.current_name == "Boston Celtics"
    assert alias is not None
    assert alias.name == "Boston Celtics"


@pytest.mark.unit
def test_derived_team_name_wins_over_caller_mapping_and_records_disagreement(
    tmp_path: Path,
    session: Session,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    html = (
        "<!doctype html><html><body>"
        + TEAM_NAME_FIXTURE.read_text(encoding="utf-8")
        + PHASE3_FIXTURE.read_text(encoding="utf-8")
        + "</body></html>"
    )
    _write_gzip(cache.path_for_url(BOS_2024_URL), html)

    report = run_full_offline_backfill(
        cache=cache,
        session=session,
        team_name_by_source={("BOS", 2024): "Stale Boston Celtics"},
    )

    entry = report.processing_report.entries[0]
    team = session.scalar(select(Team).where(Team.basketball_reference_team_id == "BOS"))
    assert [issue.code for issue in entry.team_name_issues] == [
        "team_name_override_disagreement"
    ]
    assert "Boston Celtics" in entry.team_name_issues[0].message
    assert "Stale Boston Celtics" in entry.team_name_issues[0].message
    assert team is not None
    assert team.current_name == "Boston Celtics"
    assert report.processing_report.team_name_issue_count == 1
    assert report.processing_report.team_name_issue_counts == {
        "team_name_override_disagreement": 1
    }
    processing_report_data = report.to_dict()["processing_report"]
    assert isinstance(processing_report_data, dict)
    assert processing_report_data["team_name_issue_counts"] == {
        "team_name_override_disagreement": 1
    }


@pytest.mark.unit
def test_caller_team_name_is_fallback_when_page_name_is_malformed(
    tmp_path: Path,
    session: Session,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(BOS_2024_URL), PHASE3_FIXTURE.read_text(encoding="utf-8"))

    report = run_full_offline_backfill(
        cache=cache,
        session=session,
        team_name_by_source={("BOS", 2024): "Boston Celtics"},
    )

    entry = report.processing_report.entries[0]
    team = session.scalar(select(Team).where(Team.basketball_reference_team_id == "BOS"))
    alias = session.scalar(select(TeamAlias).where(TeamAlias.abbreviation == "BOS"))
    assert entry.status == "validated"
    assert entry.team_name is None
    assert [issue.code for issue in entry.team_name_issues] == ["team_name_h1_missing"]
    assert report.processing_report.team_name_issue_count == 1
    assert report.processing_report.team_name_issue_counts == {"team_name_h1_missing": 1}
    assert team is not None
    assert team.current_name == "Boston Celtics"
    assert alias is not None
    assert alias.name == "Boston Celtics"


@pytest.mark.unit
def test_full_offline_backfill_rerun_is_idempotent(
    tmp_path: Path,
    session: Session,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(BOS_2024_URL), PHASE3_FIXTURE.read_text(encoding="utf-8"))

    first = run_full_offline_backfill(cache=cache, session=session)
    second = run_full_offline_backfill(cache=cache, session=session)

    assert first.load_report.loaded_rows == 9
    assert second.load_report.loaded_rows == 9
    assert _count(session, Season) == 1
    assert _count(session, Team) == 1
    assert _count(session, TeamAlias) == 1
    assert _count(session, TeamSeason) == 1
    assert _count(session, Player) == 1
    assert _count(session, PlayerSeason) == 1
    assert _count(session, PlayerTeamSeason) == 1


@pytest.mark.unit
def test_build_sources_uses_only_valid_inventory_entries(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    valid_path = cache.path_for_url(BOS_2024_URL)
    unsupported_path = cache.root_dir / "example.com" / "other.html.gz"
    invalid_path = cache.path_for_url(DEN_2023_URL)

    inventory = _inventory(
        cache.root_dir,
        [
            _entry(valid_path, "valid", team="BOS", season=2024),
            _entry(valid_path, "duplicate", team="BOS", season=2024),
            _entry(unsupported_path, "unsupported_path"),
            _entry(invalid_path, "invalid_or_unreadable", team="DEN", season=2023),
            _entry(cache.root_dir / "basketball-reference" / "teams-bos.html.gz", "missing_metadata"),
        ],
    )

    sources = build_offline_team_season_sources_from_inventory(inventory)

    assert len(sources) == 1
    assert sources[0].source_type == "path"
    assert sources[0].path == valid_path
    assert sources[0].team_abbreviation == "BOS"
    assert sources[0].season_year == 2024


@pytest.mark.unit
def test_backfill_skips_non_valid_inventory_entries_before_processing(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [
            _entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2024),
            _entry(cache.path_for_url(DEN_2023_URL), "duplicate", team="DEN", season=2023),
        ],
    )
    captured_sources: list[object] = []

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        captured_sources.extend(tuple(sources))
        return _processing_report([_failed_entry(error_message="synthetic processor skip")])

    monkeypatch.setattr(offline_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_backfill, "process_offline_team_season_sources", fake_process)

    report = run_full_offline_backfill(cache=cache, session=session)

    assert len(captured_sources) == 1
    assert report.selected_inventory_entries == 1
    assert report.skipped_inventory_entries == 1
    assert report.load_report.skipped_entries == 1
    assert report.audit_report.quarantined_entries == 1


@pytest.mark.unit
def test_valid_inventory_entry_without_required_metadata_fails_fast(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [CachedHtmlInventoryEntry(cache_path=str(cache.path_for_url(BOS_2024_URL)), status="valid")],
    )

    with pytest.raises(ValueError, match="team_abbreviation"):
        build_offline_team_season_sources_from_inventory(inventory)


@pytest.mark.unit
def test_loader_failure_rolls_back_partial_entry_writes(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    inventory = _inventory(
        cache.root_dir,
        [_entry(cache.path_for_url(BOS_2024_URL), "valid", team="BOS", season=2098)],
    )

    def fake_inventory(*, cache: HtmlCache) -> CachedHtmlInventory:
        return inventory

    def fake_process(sources: object, **kwargs: object) -> OfflineTeamSeasonProcessingReport:
        return _processing_report([_validated_entry(season_year=2098, rows=[_row(season_year=2098)])])

    def fail_after_write(session: Session, batch: object) -> object:
        session.add(Season(league="NBA", season_year=2098, label="2098"))
        session.flush()
        raise RuntimeError("simulated loader failure")

    monkeypatch.setattr(offline_backfill, "build_cached_html_inventory", fake_inventory)
    monkeypatch.setattr(offline_backfill, "process_offline_team_season_sources", fake_process)
    monkeypatch.setattr("nba_data.scraping.offline_loader.load_team_season_core", fail_after_write)

    report = run_full_offline_backfill(cache=cache, session=session)

    assert report.load_report.failed_entries == 1
    assert report.audit_report.quarantined_entries == 1
    assert report.audit_report.quarantine_entries[0].reason == "loading_failed"
    assert _count(session, Season) == 0


@pytest.mark.unit
def test_run_full_offline_backfill_preserves_caller_owned_commit(
    tmp_path: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(BOS_2024_URL), PHASE3_FIXTURE.read_text(encoding="utf-8"))

    def fail_commit() -> None:
        raise AssertionError("offline backfill must not commit")

    monkeypatch.setattr(session, "commit", fail_commit)

    report = run_full_offline_backfill(cache=cache, session=session)

    assert report.load_report.loaded_entries == 1
    assert _count(session, Season) == 1


@pytest.mark.unit
def test_cli_backfill_offline_refuses_without_explicit_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("CLI guard must fail before database engine creation")

    monkeypatch.setattr("nba_data.cli.main.create_db_engine", fail_engine)

    result = CliRunner().invoke(app, ["backfill", "offline"])

    assert result.exit_code != 0
    assert "Refusing offline backfill" in result.output


_FAKE_OFFLINE_BACKFILL_REPORT: dict[str, object] = {
    "selected_inventory_entries": 1,
    "loaded_entries": 1,
    "quarantine_entries": [{"team_abbreviation": "BOS", "reason": "loading_failed"}],
}


def _invoke_cli_backfill_offline_with_fake_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_path: Path | None,
) -> tuple[object, list[str]]:
    events: list[str] = []
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()

    class FakeReport:
        def to_dict(self) -> dict[str, object]:
            return _FAKE_OFFLINE_BACKFILL_REPORT

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

    def fake_backfill(*, cache: HtmlCache, session: object, max_workers: int) -> FakeReport:
        assert cache.root_dir == tmp_path / "cache"
        assert session is fake_session
        assert max_workers == 2
        events.append("backfill_run")
        return FakeReport()

    monkeypatch.setattr("nba_data.cli.main.create_db_engine", fake_engine_factory)
    monkeypatch.setattr("nba_data.cli.main.create_session_factory", fake_session_factory)
    monkeypatch.setattr("nba_data.cli.main.run_full_offline_backfill", fake_backfill)

    args = ["backfill", "offline", "--execute-approved-backfill", "--max-workers", "2"]
    if output_path is not None:
        args += ["--output", str(output_path)]

    result = CliRunner().invoke(app, args)
    return result, events


@pytest.mark.unit
def test_cli_backfill_offline_runs_with_fake_session_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "reports" / "offline-backfill.json"

    result, events = _invoke_cli_backfill_offline_with_fake_session(
        tmp_path, monkeypatch, output_path=output_path
    )

    assert result.exit_code == 0, result.output
    assert events == [
        "engine_create",
        "session_factory_create",
        "session_enter",
        "session_begin",
        "transaction_enter",
        "backfill_run",
        "transaction_exit",
        "session_exit",
        "engine_dispose",
    ]
    printed = json.loads(result.output)
    assert printed == {
        "selected_inventory_entries": 1,
        "loaded_entries": 1,
        "quarantine_entries": 1,
        "output_path": str(output_path.resolve()),
    }
    assert "BOS" not in result.output
    assert json.loads(output_path.read_text(encoding="utf-8")) == _FAKE_OFFLINE_BACKFILL_REPORT


@pytest.mark.unit
def test_cli_backfill_offline_without_output_prints_full_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _events = _invoke_cli_backfill_offline_with_fake_session(
        tmp_path, monkeypatch, output_path=None
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == _FAKE_OFFLINE_BACKFILL_REPORT


@pytest.mark.unit
def test_offline_backfill_does_not_accept_or_import_network_or_mutating_boundaries() -> None:
    signature = inspect.signature(run_full_offline_backfill)
    module_source = inspect.getsource(offline_backfill)

    assert "client" not in signature.parameters
    assert "BasketballReferenceClient" not in module_source
    assert "import requests" not in module_source
    assert "import httpx" not in module_source
    assert "cache.set" not in module_source
    assert "alembic" not in module_source
    assert ".delete(" not in module_source


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
    season_year: int = 2024,
    rows: list[dict[str, object]] | None = None,
) -> OfflineTeamSeasonEntryResult:
    normalized_rows = tuple(rows or [_row(season_year=season_year)])
    return OfflineTeamSeasonEntryResult(
        source=_source_context(season_year=season_year),
        status="validated",
        parsed_row_count=len(normalized_rows),
        normalized_rows=normalized_rows,
    )


def _failed_entry(*, error_message: str) -> OfflineTeamSeasonEntryResult:
    return OfflineTeamSeasonEntryResult(
        source=_source_context(),
        status="failed",
        error_message=error_message,
    )


def _source_context(*, season_year: int = 2024) -> OfflineTeamSeasonSourceContext:
    return OfflineTeamSeasonSourceContext(
        source_type="path",
        team_abbreviation="BOS",
        season_year=season_year,
        cache_path="cache/bos.html.gz",
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
        "values": {"games": 74},
    }
    row.update(overrides)
    return row


def _write_gzip(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
