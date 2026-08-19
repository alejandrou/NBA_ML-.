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
import nba_data.scraping.offline_player_postseason_stats_backfill as offline_player_postseason_stats_backfill
from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.db.models import (
    Player,
    PlayerPostseasonAdvanced,
    PlayerPostseasonPerGame,
    PlayerPostseasonTotals,
    PlayerSeason,
    PlayerTeamPostseasonAdvanced,
    PlayerTeamPostseasonPerGame,
    PlayerTeamPostseasonTotals,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.offline_player_postseason_stats_backfill import (
    run_offline_player_postseason_stats_backfill,
)
from nba_data.scraping.offline_player_stats_backfill import PlayerCacheRootNotFoundError
from nba_data.scraping.player_page_acquisition import build_player_page_url

HARDEN_FIXTURE = Path("tests/fixtures/html/player_page_harden_postseason.html")
BROWN_FIXTURE = Path("tests/fixtures/html/player_page_brown_postseason.html")
# One id per accepted length: 6 and 7 are the lengths discovery used to drop.
PLAYER_IDS_BY_LENGTH = ("abcde1", "abcdef1", "abcdefg1", "abcdefgh1", "abcdefghi1")
MINIMAL_PLAYER_PAGE_HTML = "<html><body><div id='content'></div></body></html>"
PLAYER_URLS = {
    "hardeja01": "https://www.basketball-reference.com/players/h/hardeja01.html",
    "brownja02": "https://www.basketball-reference.com/players/b/brownja02.html",
}

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
    PlayerPostseasonPerGame.__table__,
    PlayerPostseasonAdvanced.__table__,
    PlayerPostseasonTotals.__table__,
    PlayerTeamPostseasonPerGame.__table__,
    PlayerTeamPostseasonAdvanced.__table__,
    PlayerTeamPostseasonTotals.__table__,
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
def test_offline_player_postseason_stats_backfill_loads_harden_rows(tmp_path: Path, session: Session) -> None:
    _create_player_team_season(session, player_id="hardeja01", season_year=2021, full_name="James Harden", team_abbreviation="BRK")
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(PLAYER_URLS["hardeja01"]), HARDEN_FIXTURE.read_text(encoding="utf-8"))

    report = run_offline_player_postseason_stats_backfill(session, cache=cache)

    aggregate = session.scalar(select(PlayerPostseasonTotals))
    team = session.scalar(select(PlayerTeamPostseasonTotals))
    assert report.player_pages_processed == 1
    assert report.aggregate_rows_loaded_or_updated == 3
    assert report.team_rows_loaded_or_updated == 3
    assert report.entries_failed == 0
    assert report.rows_failed == 0
    assert report.cache_root == str((tmp_path / "cache").resolve())
    assert report.to_dict()["discovery_status"] == "ok"
    assert aggregate is not None
    assert aggregate.source_team_code == "BRK"
    assert team is not None
    assert _count(session, PlayerPostseasonTotals) == 1
    assert _count(session, PlayerTeamPostseasonTotals) == 1


@pytest.mark.unit
def test_offline_player_postseason_stats_backfill_loads_brown_rows(tmp_path: Path, session: Session) -> None:
    _create_player_team_season(session, player_id="brownja02", season_year=2024, full_name="Jaylen Brown", team_abbreviation="BOS")
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(PLAYER_URLS["brownja02"]), BROWN_FIXTURE.read_text(encoding="utf-8"))

    report = run_offline_player_postseason_stats_backfill(session, cache=cache)

    aggregate = session.scalar(select(PlayerPostseasonTotals))
    team = session.scalar(select(PlayerTeamPostseasonTotals))
    assert report.player_pages_processed == 1
    assert report.aggregate_rows_loaded_or_updated == 3
    assert report.team_rows_loaded_or_updated == 3
    assert aggregate is not None
    assert aggregate.source_team_code == "BOS"
    assert team is not None


@pytest.mark.unit
def test_cli_player_postseason_stats_refuses_without_explicit_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "player-postseason-stats-report.json"

    def fail_engine(*args: object, **kwargs: object) -> object:
        raise AssertionError("CLI guard must fail before database engine creation")

    monkeypatch.setattr(cli_main, "create_db_engine", fail_engine)

    result = CliRunner().invoke(app, ["backfill", "player-postseason-stats", "--output", str(output_path)])

    assert result.exit_code != 0
    assert "Refusing player-page postseason stats backfill" in result.output
    assert not output_path.exists()


@pytest.mark.unit
def test_cli_player_postseason_stats_runs_and_writes_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    output_path = tmp_path / "reports" / "player-postseason-stats.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()

    class FakeReport:
        def to_dict(self) -> dict[str, object]:
            return {
                "player_pages_processed": 1,
                "aggregate_rows_loaded_or_updated": 3,
                "entries_failed": 0,
                "rows_failed": 0,
                "unresolved_players_or_seasons_or_team_stints": 0,
            }

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
        assert parser_version == "player-page-postseason-parser-v4"
        events.append("player_postseason_stats_backfill_run")
        return FakeReport()

    monkeypatch.setattr(cli_main, "create_db_engine", fake_engine_factory)
    monkeypatch.setattr(cli_main, "create_session_factory", fake_session_factory)
    monkeypatch.setattr(cli_main, "run_offline_player_postseason_stats_backfill", fake_backfill)

    result = CliRunner().invoke(
        app,
        [
            "backfill",
            "player-postseason-stats",
            "--execute-approved-player-postseason-stats-backfill",
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
        "player_postseason_stats_backfill_run",
        "transaction_exit",
        "session_exit",
        "engine_dispose",
    ]
    assert json.loads(result.output) == {
        "player_pages_processed": 1,
        "aggregate_rows_loaded_or_updated": 3,
        "entries_failed": 0,
        "rows_failed": 0,
        "unresolved_players_or_seasons_or_team_stints": 0,
    }
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "player_pages_processed": 1,
        "aggregate_rows_loaded_or_updated": 3,
        "entries_failed": 0,
        "rows_failed": 0,
        "unresolved_players_or_seasons_or_team_stints": 0,
    }


@pytest.mark.unit
def test_cli_player_postseason_stats_prints_and_writes_before_nonzero_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "reports" / "player-postseason-stats-failure.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()

    class FakeReport:
        def to_dict(self) -> dict[str, object]:
            return {
                "aggregate_rows_loaded_or_updated": 3,
                "entries_failed": 1,
                "rows_failed": 2,
            }

    class FakeEngine:
        def dispose(self) -> None:
            return None

    class FakeTransaction:
        def __enter__(self) -> FakeTransaction:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    class FakeSession:
        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

        def begin(self) -> FakeTransaction:
            return FakeTransaction()

    monkeypatch.setattr(cli_main, "create_db_engine", lambda settings: FakeEngine())
    monkeypatch.setattr(cli_main, "create_session_factory", lambda engine: lambda: FakeSession())
    monkeypatch.setattr(
        cli_main,
        "run_offline_player_postseason_stats_backfill",
        lambda *args, **kwargs: FakeReport(),
    )

    try:
        result = CliRunner().invoke(
            app,
            [
                "backfill",
                "player-postseason-stats",
                "--execute-approved-player-postseason-stats-backfill",
                "--output",
                str(output_path),
            ],
        )
    finally:
        get_settings.cache_clear()

    assert result.exit_code == 1
    assert json.loads(result.output)["entries_failed"] == 1
    assert json.loads(output_path.read_text(encoding="utf-8"))["rows_failed"] == 2


@pytest.mark.unit
def test_offline_player_postseason_stats_backfill_source_has_no_network_or_client_boundaries() -> None:
    module_source = inspect.getsource(offline_player_postseason_stats_backfill)
    command_source = inspect.getsource(cli_main.backfill_player_postseason_stats)

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


@pytest.mark.unit
def test_offline_player_postseason_backfill_discovers_every_accepted_player_id_length(
    tmp_path: Path,
    session: Session,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    for player_id in PLAYER_IDS_BY_LENGTH:
        _write_gzip(cache.path_for_url(build_player_page_url(player_id)), MINIMAL_PLAYER_PAGE_HTML)

    report = run_offline_player_postseason_stats_backfill(session, cache=cache)

    assert report.player_pages_processed == len(PLAYER_IDS_BY_LENGTH)
    assert report.discovery_status == "ok"
    assert {entry.player_identifier for entry in report.entries} == set(PLAYER_IDS_BY_LENGTH)


@pytest.mark.unit
def test_offline_player_postseason_backfill_raises_when_cache_root_is_missing(
    tmp_path: Path,
    session: Session,
) -> None:
    missing_root = tmp_path / "not-created"

    with pytest.raises(PlayerCacheRootNotFoundError) as error:
        run_offline_player_postseason_stats_backfill(session, cache=HtmlCache(missing_root))

    assert str(missing_root.resolve()) in str(error.value)


@pytest.mark.unit
def test_cli_player_postseason_stats_reports_a_missing_cache_root_without_a_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The postseason command has its own copy of `except ValueError`, so it needs its
    # own guard: the shared helpers do not protect it if that handler is edited away.
    missing_root = tmp_path / "not-created"
    output_path = tmp_path / "player-postseason-stats.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(missing_root))
    monkeypatch.setenv("COLUMNS", "240")
    get_settings.cache_clear()

    class FakeEngine:
        def dispose(self) -> None:
            return None

    class FakeTransaction:
        def __enter__(self) -> FakeTransaction:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    class FakeSession:
        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

        def begin(self) -> FakeTransaction:
            return FakeTransaction()

    monkeypatch.setattr(cli_main, "create_db_engine", lambda settings: FakeEngine())
    monkeypatch.setattr(cli_main, "create_session_factory", lambda engine: lambda: FakeSession())

    try:
        result = CliRunner().invoke(
            app,
            [
                "backfill",
                "player-postseason-stats",
                "--execute-approved-player-postseason-stats-backfill",
                "--output",
                str(output_path),
            ],
        )
    finally:
        get_settings.cache_clear()

    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit)
    assert "Player-page cache root does not exist" in result.output
    assert str(missing_root.resolve()) in result.output
    assert not output_path.exists()


@pytest.mark.unit
def test_offline_player_postseason_backfill_reports_an_existing_but_unmatched_cache_root(
    tmp_path: Path,
    session: Session,
) -> None:
    empty_root = tmp_path / "cache"
    empty_root.mkdir()

    report = run_offline_player_postseason_stats_backfill(session, cache=HtmlCache(empty_root))

    assert report.player_pages_processed == 0
    assert report.discovery_status == "no_matching_pages"
    assert report.cache_root == str(empty_root.resolve())
    assert report.to_dict()["discovery_status"] == "no_matching_pages"


def _create_player_team_season(
    session: Session,
    *,
    player_id: str,
    season_year: int,
    full_name: str,
    team_abbreviation: str,
) -> PlayerTeamSeason:
    repository = CoreRepository(session)
    season = repository.get_or_create_season(league="NBA", season_year=season_year)
    team = repository.get_or_create_team(
        basketball_reference_team_id=team_abbreviation,
        current_abbreviation=team_abbreviation,
        current_name=team_abbreviation,
    )
    repository.get_or_create_team_alias(
        team=team,
        abbreviation=team_abbreviation,
        name=team_abbreviation,
        season_year=season_year,
    )
    team_season = repository.get_or_create_team_season(
        team=team,
        season=season,
        team_abbreviation=team_abbreviation,
    )
    player = repository.get_or_create_player(
        basketball_reference_player_id=player_id,
        full_name=full_name,
    )
    player_season = repository.get_or_create_player_season(player=player, season=season)
    return repository.get_or_create_player_team_season(
        player_season=player_season,
        team_season=team_season,
        roster_number="7",
        roster_position="G",
    )


def _write_gzip(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
