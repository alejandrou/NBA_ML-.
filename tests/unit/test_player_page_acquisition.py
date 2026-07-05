from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import nba_data.cli.main as cli_main
from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.db.models import Player, PlayerSeason, Season
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import RateLimitExceededError
from nba_data.scraping.player_page_acquisition import (
    PlayerPageAcquisitionConfigurationError,
    PlayerPageAcquisitionStopped,
    PlayerPageManifest,
    PlayerPageManifestEntry,
    acquire_player_page_manifest,
    build_player_page_dry_run_report,
    build_player_page_manifest,
    build_player_page_url,
    validate_player_page_acquisition_settings,
)

PLAYER_URL = "https://www.basketball-reference.com/players/h/hardeja01.html"


class FakeAcquisitionClient:
    def __init__(
        self,
        html: str = "<html>fresh</html>",
        *,
        fail_on: str | None = None,
        rate_limit_on: str | None = None,
    ) -> None:
        self.html = html
        self.fail_on = fail_on
        self.rate_limit_on = rate_limit_on
        self.calls: list[tuple[str, bool]] = []

    def get(self, url: str, *, force_refresh: bool = False) -> str:
        self.calls.append((url, force_refresh))
        if url == self.rate_limit_on:
            raise RateLimitExceededError(f"planned rate limit for {url}")
        if url == self.fail_on:
            raise RuntimeError(f"planned failure for {url}")
        return self.html


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        for table in (Season.__table__, Player.__table__, PlayerSeason.__table__):
            table.create(connection)

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as test_session:
        _seed_manifest_players(test_session)
        yield test_session

    engine.dispose()


def _seed_manifest_players(session: Session) -> None:
    season_2021 = Season(id=1, league="NBA", season_year=2021, label="2021")
    season_2022 = Season(id=2, league="NBA", season_year=2022, label="2022")
    season_2024 = Season(id=3, league="NBA", season_year=2024, label="2024")
    harden = Player(id=1, basketball_reference_player_id="hardeja01", full_name="James Harden")
    brown = Player(id=2, basketball_reference_player_id="brownja02", full_name="Jaylen Brown")
    jordan = Player(id=3, basketball_reference_player_id="jordami01", full_name="Michael Jordan")
    bey = Player(id=4, basketball_reference_player_id="beysa01", full_name="Saddiq Bey")
    qiz = Player(id=5, basketball_reference_player_id="qizh01", full_name="Qi Zhi")
    session.add_all(
        [
            season_2021,
            season_2022,
            season_2024,
            harden,
            brown,
            jordan,
            bey,
            qiz,
            PlayerSeason(player_id=1, season_id=1),
            PlayerSeason(player_id=1, season_id=2),
            PlayerSeason(player_id=2, season_id=3),
            PlayerSeason(player_id=4, season_id=3),
            PlayerSeason(player_id=5, season_id=1),
        ]
    )
    session.commit()


def _manifest(*entries: PlayerPageManifestEntry, **overrides: object) -> PlayerPageManifest:
    values: dict[str, object] = {
        "manifest_id": "player-pages-player-all-start-all-end-all-limit-all",
        "total_players": len(entries),
        "start_year": None,
        "end_year": None,
        "requested_player": None,
        "limit": None,
        "entries": tuple(entries),
    }
    values.update(overrides)
    return PlayerPageManifest(**values)


@pytest.mark.unit
def test_build_player_page_url_uses_first_letter_bucket() -> None:
    assert build_player_page_url("Hardeja01") == PLAYER_URL
    assert build_player_page_url("beysa01") == "https://www.basketball-reference.com/players/b/beysa01.html"
    assert build_player_page_url("qizh01") == "https://www.basketball-reference.com/players/q/qizh01.html"


@pytest.mark.unit
def test_player_page_manifest_filters_by_player_and_player_seasons(session: Session) -> None:
    full_manifest = build_player_page_manifest(session)
    assert [entry.player_id for entry in full_manifest.entries] == [
        "beysa01",
        "brownja02",
        "hardeja01",
        "jordami01",
        "qizh01",
    ]

    filtered = build_player_page_manifest(session, start_year=2022, end_year=2024)
    assert [entry.player_id for entry in filtered.entries] == ["beysa01", "brownja02", "hardeja01"]
    assert filtered.entries[0].matched_season_years == (2024,)
    assert filtered.entries[1].matched_season_years == (2024,)
    assert filtered.entries[2].matched_season_years == (2022,)

    one_player = build_player_page_manifest(session, player="hardeja01", start_year=2021, end_year=2021)
    assert [entry.player_id for entry in one_player.entries] == ["hardeja01"]
    assert one_player.entries[0].matched_season_years == (2021,)


@pytest.mark.unit
def test_player_page_dry_run_reports_cache_hits(tmp_path: Path, session: Session) -> None:
    cache = HtmlCache(tmp_path / "cache")
    cache.set(PLAYER_URL, "<html>cached</html>")

    report = build_player_page_dry_run_report(session, cache=cache, player="hardeja01")

    assert report.total_players == 1
    assert report.cache_hits == 1
    assert report.missing_cache_entries == 0
    assert report.estimated_fetch_count == 0
    assert report.entries[0].cache_status == "hit"


@pytest.mark.unit
def test_player_page_acquisition_cache_hit_makes_no_client_request(tmp_path: Path) -> None:
    entry = PlayerPageManifestEntry(
        player_id="hardeja01",
        first_letter="h",
        url=PLAYER_URL,
        matched_season_years=(2021,),
    )
    manifest = _manifest(entry)
    cache = HtmlCache(tmp_path / "cache")
    cache.set(PLAYER_URL, "<html>cached</html>")
    client = FakeAcquisitionClient("<html>fresh</html>")

    report = acquire_player_page_manifest(manifest, cache=cache, client=client)

    assert client.calls == []
    assert cache.get(PLAYER_URL) == "<html>cached</html>"
    assert report.cache_hits == 1
    assert report.fetched == 0
    assert report.failures == 0
    assert report.live_request_count == 0
    assert report.entries[0].status == "cache_hit"


@pytest.mark.unit
def test_player_page_acquisition_report_includes_partial_failure(tmp_path: Path) -> None:
    harden = PlayerPageManifestEntry(
        player_id="hardeja01",
        first_letter="h",
        url=PLAYER_URL,
        matched_season_years=(2021,),
    )
    brown = PlayerPageManifestEntry(
        player_id="brownja02",
        first_letter="b",
        url="https://www.basketball-reference.com/players/b/brownja02.html",
        matched_season_years=(2024,),
    )
    manifest = _manifest(harden, brown, total_players=2)
    cache = HtmlCache(tmp_path / "cache")
    cache.set(PLAYER_URL, "<html>cached</html>")
    client = FakeAcquisitionClient(fail_on=brown.url)

    with pytest.raises(PlayerPageAcquisitionStopped) as exc_info:
        acquire_player_page_manifest(manifest, cache=cache, client=client)

    report = exc_info.value.report
    assert report.total_players == 2
    assert report.processed_entries == 2
    assert report.cache_hits == 1
    assert report.fetched == 0
    assert report.failures == 1
    assert report.rate_limited == 0
    assert report.live_request_count == 1
    assert report.completed is False
    assert report.stopped_reason == "failed"
    assert report.stopped_at_entry == 2
    assert [entry.status for entry in report.entries] == ["cache_hit", "failed"]


@pytest.mark.unit
def test_player_page_manifest_and_acquisition_do_not_write_db_rows(
    tmp_path: Path,
    session: Session,
) -> None:
    statements: list[str] = []

    def capture(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(session.bind, "before_cursor_execute", capture)
    try:
        manifest = build_player_page_manifest(session, player="hardeja01", start_year=2021, end_year=2021)
        cache = HtmlCache(tmp_path / "cache")
        client = FakeAcquisitionClient("<!doctype html><html>fresh</html>")
        report = acquire_player_page_manifest(manifest, cache=cache, client=client)
    finally:
        event.remove(session.bind, "before_cursor_execute", capture)

    assert report.fetched == 1
    assert statements
    assert all(
        not statement.lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP")
        )
        for statement in statements
    )


@pytest.mark.unit
def test_player_page_acquisition_settings_reject_rate_limit_above_10(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "11")
    get_settings.cache_clear()

    with pytest.raises(PlayerPageAcquisitionConfigurationError, match="10 requests/minute"):
        validate_player_page_acquisition_settings(get_settings())


@pytest.mark.unit
def test_cli_dry_run_player_pages_runs_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    output_path = tmp_path / "reports" / "dry-run-player-pages.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()

    class FakeEngine:
        def dispose(self) -> None:
            events.append("engine_dispose")

    class FakeSession:
        def __enter__(self) -> FakeSession:
            events.append("session_enter")
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            events.append("session_exit")

    class FakeReport:
        def to_dict(self) -> dict[str, object]:
            return {"total_players": 1, "cache_hits": 1, "entries": []}

    fake_engine = FakeEngine()
    fake_session = FakeSession()

    def fake_engine_factory(settings: object) -> FakeEngine:
        events.append("engine_create")
        return fake_engine

    def fake_session_factory(engine: object) -> object:
        assert engine is fake_engine
        events.append("session_factory_create")
        return lambda: fake_session

    def fake_dry_run(
        session: object,
        *,
        cache: HtmlCache,
        limit: int | None,
        player: str | None,
        start_year: int | None,
        end_year: int | None,
    ) -> FakeReport:
        assert session is fake_session
        assert cache.root_dir == tmp_path / "cache"
        assert limit == 2
        assert player == "hardeja01"
        assert start_year == 2021
        assert end_year == 2021
        events.append("dry_run_build")
        return FakeReport()

    monkeypatch.setattr(cli_main, "create_db_engine", fake_engine_factory)
    monkeypatch.setattr(cli_main, "create_session_factory", fake_session_factory)
    monkeypatch.setattr(cli_main, "build_player_page_dry_run_report", fake_dry_run)

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "dry-run-player-pages",
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
        "dry_run_build",
        "session_exit",
        "engine_dispose",
    ]
    assert json.loads(result.output) == {"total_players": 1, "cache_hits": 1, "entries": []}
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "total_players": 1,
        "cache_hits": 1,
        "entries": [],
    }


@pytest.mark.unit
def test_cli_acquire_player_pages_refuses_without_approval_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_clients: list[object] = []

    class FakeBasketballReferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created_clients.append(self)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", FakeBasketballReferenceClient)

    result = CliRunner().invoke(app, ["acquisition", "acquire-player-pages"])

    assert result.exit_code != 0
    assert "Refusing acquisition" in result.output
    assert created_clients == []


@pytest.mark.unit
def test_cli_acquire_player_pages_runs_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    output_path = tmp_path / "reports" / "player-pages-acquisition.json"
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    fake_instances: list[FakeAcquisitionClient] = []

    manifest = _manifest(
        PlayerPageManifestEntry(
            player_id="hardeja01",
            first_letter="h",
            url=PLAYER_URL,
            matched_season_years=(2021,),
        )
    )

    class FakeEngine:
        def dispose(self) -> None:
            events.append("engine_dispose")

    class FakeSession:
        def __enter__(self) -> FakeSession:
            events.append("session_enter")
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            events.append("session_exit")

    class FakeBasketballReferenceClient(FakeAcquisitionClient):
        def __init__(self, settings: object, *, max_429_retries: int) -> None:
            super().__init__("<!doctype html><html>cli fresh</html>")
            self.settings = settings
            self.max_429_retries = max_429_retries
            fake_instances.append(self)
            events.append("client_create")

        def __enter__(self) -> FakeBasketballReferenceClient:
            events.append("client_enter")
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            events.append("client_exit")

    fake_engine = FakeEngine()
    fake_session = FakeSession()

    def fake_engine_factory(settings: object) -> FakeEngine:
        events.append("engine_create")
        return fake_engine

    def fake_session_factory(engine: object) -> object:
        assert engine is fake_engine
        events.append("session_factory_create")
        return lambda: fake_session

    def fake_manifest_builder(
        session: object,
        *,
        limit: int | None,
        player: str | None,
        start_year: int | None,
        end_year: int | None,
    ) -> PlayerPageManifest:
        assert session is fake_session
        assert limit == 2
        assert player == "hardeja01"
        assert start_year == 2021
        assert end_year == 2021
        events.append("manifest_build")
        return manifest

    monkeypatch.setattr(cli_main, "create_db_engine", fake_engine_factory)
    monkeypatch.setattr(cli_main, "create_session_factory", fake_session_factory)
    monkeypatch.setattr(cli_main, "build_player_page_manifest", fake_manifest_builder)
    monkeypatch.setattr(cli_main, "BasketballReferenceClient", FakeBasketballReferenceClient)

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-player-pages",
            "--owner-approved",
            "--execute-approved-manifest",
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
    assert len(fake_instances) == 1
    assert fake_instances[0].max_429_retries == 0
    assert fake_instances[0].calls == [(PLAYER_URL, False)]
    assert events == [
        "engine_create",
        "session_factory_create",
        "session_enter",
        "manifest_build",
        "session_exit",
        "engine_dispose",
        "client_create",
        "client_enter",
        "client_exit",
    ]
    report = json.loads(result.output)
    assert report["fetched"] == 1
    assert report["live_request_count"] == 1
    assert json.loads(output_path.read_text(encoding="utf-8")) == report
    assert HtmlCache(tmp_path / "cache").get(PLAYER_URL) == "<!doctype html><html>cli fresh</html>"
