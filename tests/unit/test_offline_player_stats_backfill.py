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
import nba_data.scraping.player_page_acquisition as player_page_acquisition
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
from nba_data.scraping.offline_player_stats_backfill import (
    PlayerCacheRootNotFoundError,
    _discover_player_cache_entries,
    run_offline_player_stats_backfill,
)
from nba_data.scraping.player_page_acquisition import build_player_page_url

FIXTURE = Path("tests/fixtures/html/player_page_harden_regular_season.html")
PLAYER_URL = "https://www.basketball-reference.com/players/h/hardeja01.html"
# One id per accepted length: 6 and 7 are the lengths discovery used to drop.
PLAYER_IDS_BY_LENGTH = ("abcde1", "abcdef1", "abcdefg1", "abcdefgh1", "abcdefghi1")
MINIMAL_PLAYER_PAGE_HTML = "<html><body><div id='content'></div></body></html>"

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
    assert report.entries_failed == 0
    assert report.rows_failed == 0
    assert report.cache_root == str((tmp_path / "cache").resolve())
    assert report.to_dict()["discovery_status"] == "ok"
    assert totals is not None
    assert totals.source_team_code == "2TM"
    assert _count(session, PlayerSeasonTotals) == 1


@pytest.mark.unit
def test_offline_player_stats_backfill_supports_real_cache_player_page_columns(
    tmp_path: Path,
    session: Session,
) -> None:
    _create_player_season(session)
    cache = HtmlCache(tmp_path / "cache")
    cache_path = cache.path_for_url(PLAYER_URL)
    _write_gzip(
        cache_path,
        """
        <html><body>
        <table id="totals_stats">
          <thead>
            <tr>
              <th data-stat="year_id">Season</th>
              <th data-stat="team_name_abbr">Tm</th>
              <th data-stat="comp_name_abbr">Lg</th>
              <th data-stat="games">G</th>
              <th data-stat="pts">PTS</th>
            </tr>
          </thead>
          <tbody>
            <tr><th data-stat="year_id">2020-21</th><td data-stat="team_name_abbr">2TM</td><td data-stat="comp_name_abbr">NBA</td><td data-stat="games">44</td><td data-stat="pts">1083</td></tr>
            <tr><th data-stat="year_id">2020-21</th><td data-stat="team_name_abbr">HOU</td><td data-stat="comp_name_abbr">NBA</td><td data-stat="games">8</td><td data-stat="pts">199</td></tr>
            <tr><th data-stat="year_id">2020-21</th><td data-stat="team_name_abbr">BRK</td><td data-stat="comp_name_abbr">NBA</td><td data-stat="games">36</td><td data-stat="pts">884</td></tr>
          </tbody>
        </table>
        </body></html>
        """,
    )

    report = run_offline_player_stats_backfill(session, cache=cache)

    totals = session.scalar(select(PlayerSeasonTotals))
    assert report.player_pages_processed == 1
    assert report.tables_parsed == 1
    assert report.rows_selected == 1
    assert report.rows_loaded_or_updated == 1
    assert report.unresolved_players_or_seasons == 0
    assert totals is not None
    assert totals.source_team_code == "2TM"
    assert totals.g == 44
    assert totals.pts == 1083


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
            return {
                "player_pages_processed": 1,
                "rows_loaded_or_updated": 8,
                "entries_failed": 0,
                "rows_failed": 0,
                "unresolved_players_or_seasons": 0,
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
        assert parser_version == "player-page-parser-v4"
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
    assert json.loads(result.output) == {
        "player_pages_processed": 1,
        "rows_loaded_or_updated": 8,
        "entries_failed": 0,
        "rows_failed": 0,
        "unresolved_players_or_seasons": 0,
        "output_path": str(output_path.resolve()),
    }
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "player_pages_processed": 1,
        "rows_loaded_or_updated": 8,
        "entries_failed": 0,
        "rows_failed": 0,
        "unresolved_players_or_seasons": 0,
    }


@pytest.mark.unit
def test_cli_player_stats_prints_and_writes_before_nonzero_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "reports" / "player-stats-failure.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()

    class FakeReport:
        def to_dict(self) -> dict[str, object]:
            return {
                "rows_loaded_or_updated": 8,
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
        "run_offline_player_stats_backfill",
        lambda *args, **kwargs: FakeReport(),
    )

    try:
        result = CliRunner().invoke(
            app,
            [
                "backfill",
                "player-stats",
                "--execute-approved-player-stats-backfill",
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


@pytest.mark.unit
def test_offline_player_stats_backfill_discovers_every_accepted_player_id_length(
    tmp_path: Path,
    session: Session,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    for player_id in PLAYER_IDS_BY_LENGTH:
        _write_gzip(cache.path_for_url(build_player_page_url(player_id)), MINIMAL_PLAYER_PAGE_HTML)

    discovered = _discover_player_cache_entries(cache.root_dir, player_identifier=None)
    report = run_offline_player_stats_backfill(session, cache=cache)

    assert {player_id for _, player_id, _ in discovered} == set(PLAYER_IDS_BY_LENGTH)
    assert report.player_pages_processed == len(PLAYER_IDS_BY_LENGTH)
    assert report.discovery_status == "ok"
    assert {entry.player_identifier for entry in report.entries} == set(PLAYER_IDS_BY_LENGTH)


@pytest.mark.unit
@pytest.mark.parametrize("length", range(1, 14))
def test_cache_discovery_and_acquisition_agree_on_player_id_length_range(length: int) -> None:
    player_id = "a" * (length - 1) + "1"
    filename = f"players-{player_id[0]}-{player_id}.html-{'0' * 16}.html.gz"

    acquisition_accepts = player_page_acquisition._PLAYER_ID_RE.fullmatch(player_id) is not None
    discovery_accepts = (
        offline_player_stats_backfill._PLAYER_CACHE_FILE_RE.fullmatch(filename) is not None
    )

    assert discovery_accepts == acquisition_accepts


@pytest.mark.unit
def test_offline_player_stats_backfill_still_rejects_malformed_cache_filenames(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(PLAYER_URL), MINIMAL_PLAYER_PAGE_HTML)
    cache_dir = cache.path_for_url(PLAYER_URL).parent
    for malformed_name in (
        "player-h-hardeja01.html-0123456789abcdef.html.gz",
        "players-h-hardeja01.html.html.gz",
        "players-h-hardeja01.html-0123456789abcdef.html",
        "players-h-hardeja01.html-zzzzzzzzzzzzzzzz.html.gz",
        "players-hh-hardeja01.html-0123456789abcdef.html.gz",
    ):
        _write_gzip(cache_dir / malformed_name, MINIMAL_PLAYER_PAGE_HTML)

    discovered = _discover_player_cache_entries(cache.root_dir, player_identifier=None)

    assert [player_id for _, player_id, _ in discovered] == ["hardeja01"]


@pytest.mark.unit
def test_cache_discovery_rejects_player_ids_acquisition_cannot_write(
    tmp_path: Path,
) -> None:
    # Discovery used to accept a leading digit; sharing PLAYER_ID_PATTERN narrows
    # it to match acquisition. Acquisition can never write such an id, so nothing
    # reachable is lost — but the narrowing is deliberate, so pin it.
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(PLAYER_URL), MINIMAL_PLAYER_PAGE_HTML)
    cache_dir = cache.path_for_url(PLAYER_URL).parent
    _write_gzip(
        cache_dir / "players-1-1ardeja01.html-0123456789abcdef.html.gz",
        MINIMAL_PLAYER_PAGE_HTML,
    )

    discovered = _discover_player_cache_entries(cache.root_dir, player_identifier=None)

    assert [player_id for _, player_id, _ in discovered] == ["hardeja01"]
    assert player_page_acquisition._PLAYER_ID_RE.fullmatch("1ardeja01") is None


@pytest.mark.unit
def test_offline_player_stats_backfill_raises_when_cache_root_is_missing(
    tmp_path: Path,
    session: Session,
) -> None:
    missing_root = tmp_path / "not-created"

    with pytest.raises(PlayerCacheRootNotFoundError) as error:
        run_offline_player_stats_backfill(session, cache=HtmlCache(missing_root))

    assert str(missing_root.resolve()) in str(error.value)


@pytest.mark.unit
def test_cli_player_stats_reports_a_missing_cache_root_without_a_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The backfill raises PlayerCacheRootNotFoundError(ValueError) so the command's
    # existing `except ValueError` turns it into a clean non-zero exit. Nothing else
    # pins that, and the real run function is used here on purpose.
    missing_root = tmp_path / "not-created"
    output_path = tmp_path / "player-stats.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(missing_root))
    # Typer renders errors in a Rich panel that hard-wraps a long absolute path at
    # the terminal width. Widen it so this asserts on the message, not the wrapping.
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
                "player-stats",
                "--execute-approved-player-stats-backfill",
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
def test_offline_player_stats_backfill_reports_an_existing_but_unmatched_cache_root(
    tmp_path: Path,
    session: Session,
) -> None:
    empty_root = tmp_path / "cache"
    empty_root.mkdir()

    report = run_offline_player_stats_backfill(session, cache=HtmlCache(empty_root))

    assert report.player_pages_processed == 0
    assert report.discovery_status == "no_matching_pages"
    assert report.cache_root == str(empty_root.resolve())
    assert report.to_dict()["discovery_status"] == "no_matching_pages"


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
