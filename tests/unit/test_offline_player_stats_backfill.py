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

import nba_data.cli.main as cli_main
import nba_data.scraping.offline_player_stats_backfill as offline_player_stats_backfill
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
from nba_data.scraping.offline_player_stats_backfill import run_offline_player_stats_backfill

FIXTURE = Path("tests/fixtures/html/player_page_harden_regular_season.html")
PLAYER_URL = "https://www.basketball-reference.com/players/h/hardeja01.html"

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
    PlayerSeasonAdjShooting.__table__,
    PlayerSeasonPbp.__table__,
    PlayerSeasonShooting.__table__,
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
def test_offline_player_stats_backfill_loads_selected_rows_from_cached_player_page(
    tmp_path: Path,
    session: Session,
) -> None:
    _create_player_season(session)
    cache = HtmlCache(tmp_path / "cache")
    cache_path = cache.path_for_url(PLAYER_URL)
    _write_gzip(cache_path, FIXTURE.read_text(encoding="utf-8"))

    report = run_offline_player_stats_backfill(session, cache=cache)

    totals = session.scalar(select(PlayerSeasonTotals))
    assert report.player_pages_processed == 1
    assert report.rows_selected == 8
    assert report.rows_loaded_or_updated == 8
    assert report.unresolved_players_or_seasons == 0
    assert totals is not None
    assert totals.source_team_code == "2TM"
    assert _count(session, PlayerSeasonTotals) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"limit": 0}, "limit"),
        ({"player": " "}, "player"),
        ({"start_year": 2025, "end_year": 2024}, "start_year"),
        ({"parser_version": " "}, "parser_version"),
    ),
)
def test_offline_player_stats_backfill_rejects_invalid_arguments(
    tmp_path: Path,
    session: Session,
    kwargs: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        run_offline_player_stats_backfill(session, cache=HtmlCache(tmp_path / "cache"), **kwargs)


@pytest.mark.unit
def test_cli_player_stats_refuses_without_explicit_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "player-stats-report.json"

    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("CLI guard must fail before database engine creation")

    monkeypatch.setattr(cli_main, "create_db_engine", fail_engine)

    result = CliRunner().invoke(app, ["backfill", "player-stats", "--output", str(output_path)])

    assert result.exit_code != 0
    assert "Refusing player-page stats backfill" in result.output
    assert not output_path.exists()


@pytest.mark.unit
def test_cli_player_stats_runs_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    output_path = tmp_path / "reports" / "player-stats.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()

    class FakeReport:
        def to_dict(self) -> dict[str, object]:
            return {"player_pages_processed": 1, "rows_loaded_or_updated": 8}

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
        limit: int | None,
        player: str | None,
        start_year: int | None,
        end_year: int | None,
        parser_version: str,
    ) -> FakeReport:
        assert session is fake_session
        assert cache.root_dir == tmp_path / "cache"
        assert limit == 2
        assert player == "hardeja01"
        assert start_year == 2021
        assert end_year == 2021
        assert parser_version == "player-page-parser-v1"
        events.append("player_stats_backfill_run")
        return FakeReport()

    monkeypatch.setattr(cli_main, "create_db_engine", fake_engine_factory)
    monkeypatch.setattr(cli_main, "create_session_factory", fake_session_factory)
    monkeypatch.setattr(cli_main, "run_offline_player_stats_backfill", fake_backfill)

    result = CliRunner().invoke(
        app,
        [
            "backfill",
            "player-stats",
            "--execute-approved-player-stats-backfill",
            "--limit",
            "2",
            "--player",
            "hardeja01",
            "--start-year",
            "2021",
            "--end-year",
            "2021",
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
        "player_stats_backfill_run",
        "transaction_exit",
        "session_exit",
        "engine_dispose",
    ]
    assert json.loads(result.output) == {"player_pages_processed": 1, "rows_loaded_or_updated": 8}
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "player_pages_processed": 1,
        "rows_loaded_or_updated": 8,
    }


@pytest.mark.unit
def test_offline_player_stats_backfill_source_has_no_network_or_client_boundaries() -> None:
    module_source = inspect.getsource(offline_player_stats_backfill)
    command_source = inspect.getsource(cli_main.backfill_player_stats)

    for source in (module_source, command_source):
        for forbidden in (
            "BasketballReferenceClient",
            "import requests",
            "import httpx",
            "cache.set",
            ".commit(",
            ".rollback(",
        ):
            assert forbidden not in source


def _create_player_season(session: Session) -> PlayerSeason:
    repository = CoreRepository(session)
    season = repository.get_or_create_season(league="NBA", season_year=2021)
    player = repository.get_or_create_player(
        basketball_reference_player_id="hardeja01",
        full_name="James Harden",
    )
    return repository.get_or_create_player_season(player=player, season=season)


def _write_gzip(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
