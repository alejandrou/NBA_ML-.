from __future__ import annotations

import gzip
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.config.settings import MINIMUM_SCRAPER_DELAY_SECONDS, Settings, get_settings
from nba_data.scraping import cache_writer
from nba_data.scraping.cache import CacheFetchMetadata, HtmlCache
from nba_data.scraping.cache_writer import CacheWriteError, write_html_to_cache_safely
from nba_data.scraping.client import FetchResult, RateLimitExceededError
from nba_data.scraping.game_pilot_acquisition import (
    GamePilotAcquisitionConfigurationError,
    GamePilotAcquisitionStopped,
    acquire_game_pilot_manifest,
    build_game_pilot_dry_run_report,
    validate_game_pilot_acquisition_settings,
    validate_settings_within_manifest_policy,
)
from nba_data.scraping.game_pilot_manifest import (
    GamePilotManifest,
    validate_game_pilot_manifest,
)

SCHEDULE_URL = "https://www.basketball-reference.com/leagues/NBA_2024_games.html"
BOX_URL = "https://www.basketball-reference.com/boxscores/202310240DEN.html"
PBP_URL = "https://www.basketball-reference.com/boxscores/pbp/202310240DEN.html"
FETCHED_AT = datetime(2026, 9, 23, 12, 0, 0, tzinfo=UTC)
PAGE = "<!DOCTYPE html><html><body>page</body></html>"


def _fetch_metadata() -> CacheFetchMetadata:
    return CacheFetchMetadata(fetched_at=FETCHED_AT, http_status=200, final_url=BOX_URL)


def _raw_manifest(*, requests_per_minute: int = 10) -> dict[str, object]:
    return {
        "manifest_id": "f8-001-test",
        "status": "approved",
        "approved_by_owner": True,
        "approved_at": "2026-09-23T12:00:00Z",
        "approval_basis": "Test fixture approval.",
        "scope": {"page_types": ["league_schedule", "box_score", "play_by_play"], "max_urls": 3},
        "acquisition_policy": {
            "cache_first": True,
            "sequential": True,
            "stop_on_first_failure": True,
            "requests_per_minute": requests_per_minute,
            "max_requests_per_minute": 20,
            "write_target": "HtmlCache .html.gz",
        },
        "entries": [
            {
                "page_type": "league_schedule",
                "url": SCHEDULE_URL,
                "season_end_year": 2024,
                "reason": "Season index.",
            },
            {
                "page_type": "box_score",
                "url": BOX_URL,
                "season_end_year": 2024,
                "game_id": "202310240DEN",
                "reason": "Opening night.",
            },
            {
                "page_type": "play_by_play",
                "url": PBP_URL,
                "season_end_year": 2024,
                "game_id": "202310240DEN",
                "reason": "Opening night.",
            },
        ],
    }


def _manifest(**kwargs: int) -> GamePilotManifest:
    return validate_game_pilot_manifest(_raw_manifest(**kwargs))


def _write_manifest(tmp_path: Path, **kwargs: int) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_raw_manifest(**kwargs)), encoding="utf-8")
    return path


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "scraper_user_agent": "nba-data-tests/0.1",
        "scraper_max_requests_per_minute": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakePilotClient:
    """Counts requests the way the real client does; each fetch costs 7 fake seconds."""

    def __init__(
        self,
        *,
        clock: FakeClock | None = None,
        html: str = PAGE,
        fail_on: str | None = None,
        rate_limit_on: str | None = None,
        retries_on: str | None = None,
    ) -> None:
        self.clock = clock or FakeClock()
        self.html = html
        self.fail_on = fail_on
        self.rate_limit_on = rate_limit_on
        self.retries_on = retries_on
        self.calls: list[tuple[str, bool]] = []
        self._request_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    def fetch(self, url: str, *, force_refresh: bool = False) -> FetchResult:
        self.calls.append((url, force_refresh))
        self._request_count += 2 if url == self.retries_on else 1
        self.clock.now += 7.0
        if url == self.rate_limit_on:
            msg = f"planned rate limit for {url}"
            raise RateLimitExceededError(msg)
        if url == self.fail_on:
            msg = f"planned failure for {url}"
            raise RuntimeError(msg)
        metadata = CacheFetchMetadata(fetched_at=FETCHED_AT, http_status=200, final_url=url)
        return FetchResult(html=self.html, metadata=metadata)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.mark.unit
def test_dry_run_reports_hits_misses_and_the_minimum_duration(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(SCHEDULE_URL, PAGE)

    report = build_game_pilot_dry_run_report(_manifest(), cache=cache, settings=_settings())

    assert report.total_entries == 3
    assert report.games == 1
    assert report.cache_hits == 1
    assert report.missing_cache_entries == 2
    assert report.estimated_fetch_count == 2
    assert report.estimated_minimum_seconds == MINIMUM_SCRAPER_DELAY_SECONDS
    assert [entry.cache_status for entry in report.entries] == ["hit", "missing", "missing"]


@pytest.mark.unit
def test_cache_hits_cost_no_request_and_are_never_overwritten(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    for url in (SCHEDULE_URL, BOX_URL, PBP_URL):
        cache.set(url, "<html>cached</html>")
    client = FakePilotClient()

    report = acquire_game_pilot_manifest(
        _manifest(), cache=cache, client=client, clock=client.clock
    )

    assert client.calls == []
    assert report.cache_hits == 3
    assert report.live_request_count == 0
    assert report.completed is True
    assert cache.get(BOX_URL) == "<html>cached</html>"


@pytest.mark.unit
def test_misses_are_fetched_once_written_with_provenance_and_measured(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(SCHEDULE_URL, PAGE)
    client = FakePilotClient(retries_on=PBP_URL)

    report = acquire_game_pilot_manifest(
        _manifest(), cache=cache, client=client, clock=client.clock
    )

    assert client.calls == [(BOX_URL, False), (PBP_URL, False)]
    assert report.completed is True
    assert report.fetched == 2
    assert report.live_request_count == 3
    assert report.wall_seconds == 14.0
    box, pbp = report.entries[1], report.entries[2]
    assert box.status == "fetched"
    assert box.requests == 1
    assert pbp.requests == 2
    assert box.http_status == 200
    assert box.fetched_at == FETCHED_AT.isoformat()
    assert box.bytes == len(PAGE.encode("utf-8"))
    assert box.compressed_bytes == Path(box.cache_path).stat().st_size
    assert box.elapsed_seconds == 7.0
    assert report.fetched_bytes == 2 * len(PAGE.encode("utf-8"))
    assert cache.get(BOX_URL) == PAGE
    assert cache.get_metadata(BOX_URL) == CacheFetchMetadata(
        fetched_at=FETCHED_AT, http_status=200, final_url=BOX_URL
    )


@pytest.mark.unit
@pytest.mark.parametrize("html", ["", "   ", '{"not": "html"}'])
def test_empty_or_non_html_content_stops_before_any_cache_write(tmp_path: Path, html: str) -> None:
    cache = HtmlCache(tmp_path)
    client = FakePilotClient(html=html)

    with pytest.raises(GamePilotAcquisitionStopped) as raised:
        acquire_game_pilot_manifest(_manifest(), cache=cache, client=client, clock=client.clock)

    report = raised.value.report
    assert report.stopped_reason == "failed"
    assert report.stopped_at_entry == 1
    assert report.live_request_count == 1
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.unit
def test_a_429_stops_the_run_with_a_partial_report(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    client = FakePilotClient(rate_limit_on=BOX_URL)

    with pytest.raises(GamePilotAcquisitionStopped) as raised:
        acquire_game_pilot_manifest(_manifest(), cache=cache, client=client, clock=client.clock)

    report = raised.value.report
    assert client.calls == [(SCHEDULE_URL, False), (BOX_URL, False)]
    assert report.completed is False
    assert report.stopped_reason == "rate_limited"
    assert report.stopped_at_entry == 2
    assert report.processed_entries == 2
    assert report.rate_limited == 1
    assert report.live_request_count == 2
    assert report.entries[1].error_details == f"planned rate limit for {BOX_URL}"
    assert not cache.exists(BOX_URL)


@pytest.mark.unit
def test_any_other_failure_stops_the_run_with_a_partial_report(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    client = FakePilotClient(fail_on=PBP_URL)

    with pytest.raises(GamePilotAcquisitionStopped) as raised:
        acquire_game_pilot_manifest(_manifest(), cache=cache, client=client, clock=client.clock)

    report = raised.value.report
    assert report.stopped_reason == "failed"
    assert report.stopped_at_entry == 3
    assert report.fetched == 2
    assert report.failures == 1
    assert cache.exists(BOX_URL)
    assert not cache.exists(PBP_URL)


@pytest.mark.unit
def test_the_writer_refuses_an_orphan_sidecar_and_leaves_it_untouched(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    sidecar = cache.metadata_path_for_url(BOX_URL)
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("{}", encoding="utf-8")

    with pytest.raises(CacheWriteError, match="existing cache metadata file"):
        write_html_to_cache_safely(cache, BOX_URL, PAGE)

    assert not cache.exists(BOX_URL)
    assert sidecar.read_text(encoding="utf-8") == "{}"


@pytest.mark.unit
def test_the_writer_refuses_to_overwrite_a_body(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(BOX_URL, "<html>first</html>")

    with pytest.raises(CacheWriteError, match="existing cache file"):
        write_html_to_cache_safely(cache, BOX_URL, PAGE)

    assert cache.get(BOX_URL) == "<html>first</html>"


@pytest.mark.unit
def test_the_publish_refuses_a_body_another_writer_created_after_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = HtmlCache(tmp_path)
    # The existence check ran before the other writer published: it saw nothing.
    monkeypatch.setattr(cache_writer, "_refuse_existing", lambda *paths: None)
    cache.set(BOX_URL, "<html>first</html>")

    with pytest.raises(CacheWriteError, match="existing cache file"):
        write_html_to_cache_safely(cache, BOX_URL, PAGE, metadata=_fetch_metadata())

    assert cache.get(BOX_URL) == "<html>first</html>"
    assert not cache.metadata_path_for_url(BOX_URL).exists()
    assert list(cache.path_for_url(BOX_URL).parent.glob(".*.tmp")) == []


@pytest.mark.unit
def test_a_sidecar_created_after_the_check_rolls_back_the_body_and_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = HtmlCache(tmp_path)
    sidecar = cache.metadata_path_for_url(BOX_URL)
    write_metadata = cache_writer.write_cache_fetch_metadata

    def another_writer_leaves_a_sidecar(path: Path, metadata: CacheFetchMetadata) -> None:
        write_metadata(path, metadata)
        sidecar.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cache_writer, "write_cache_fetch_metadata", another_writer_leaves_a_sidecar)

    with pytest.raises(CacheWriteError, match="existing cache metadata file"):
        write_html_to_cache_safely(cache, BOX_URL, PAGE, metadata=_fetch_metadata())

    assert not cache.exists(BOX_URL)
    assert sidecar.read_text(encoding="utf-8") == "{}"
    assert list(sidecar.parent.glob(".*.tmp")) == []


@pytest.mark.unit
def test_the_rollback_never_removes_a_body_another_writer_put_in_its_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = HtmlCache(tmp_path)
    body = cache.path_for_url(BOX_URL)
    publish = cache_writer._publish

    def body_replaced_then_sidecar_fails(temp_path: Path, final_path: Path, what: str) -> None:
        if final_path != body:
            raise OSError("disk full")
        publish(temp_path, final_path, what)
        replacement = tmp_path / "replacement.html.gz"
        with gzip.open(replacement, "wt", encoding="utf-8") as file:
            file.write("<html>other writer</html>")
        os.replace(replacement, body)

    monkeypatch.setattr(cache_writer, "_publish", body_replaced_then_sidecar_fails)

    with pytest.raises(OSError, match="disk full"):
        write_html_to_cache_safely(cache, BOX_URL, PAGE, metadata=_fetch_metadata())

    assert cache.get(BOX_URL) == "<html>other writer</html>"
    assert list(body.parent.glob(".*.tmp")) == []


@pytest.mark.unit
def test_the_writer_preserves_crlf_bytes(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    html = "<!DOCTYPE html>\r\n<html>\r\n</html>\r\n"

    path = write_html_to_cache_safely(cache, BOX_URL, html)

    with gzip.open(path, "rt", encoding="utf-8", newline="") as file:
        assert file.read() == html
    assert list(path.parent.glob(".*.tmp")) == []


@pytest.mark.unit
def test_settings_above_ten_requests_per_minute_are_refused() -> None:
    with pytest.raises(GamePilotAcquisitionConfigurationError, match="10 requests/minute"):
        validate_game_pilot_acquisition_settings(_settings(scraper_max_requests_per_minute=11))


@pytest.mark.unit
def test_settings_faster_than_the_manifest_approves_are_refused() -> None:
    manifest = _manifest(requests_per_minute=6)

    with pytest.raises(GamePilotAcquisitionConfigurationError, match="the manifest approves"):
        validate_settings_within_manifest_policy(_settings(), manifest)
    validate_settings_within_manifest_policy(_settings(scraper_max_requests_per_minute=6), manifest)


def _forbid_client_creation(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    created: list[object] = []

    class ForbiddenClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created.append(self)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", ForbiddenClient)
    return created


@pytest.mark.unit
@pytest.mark.parametrize(
    "flags",
    [[], ["--owner-approved"], ["--execute-approved-manifest"]],
)
def test_cli_refuses_without_both_flags_before_reading_the_manifest(
    flags: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    read: list[object] = []
    monkeypatch.setattr(
        "nba_data.cli.main.load_game_pilot_manifest",
        lambda path: read.append(path),
    )

    result = CliRunner().invoke(
        app,
        ["acquisition", "acquire-game-pilot", str(tmp_path / "absent.json"), *flags],
    )

    assert result.exit_code == 1
    assert "Refusing acquisition without --owner-approved and --execute-approved-manifest" in (
        result.output
    )
    assert read == []
    assert created == []


@pytest.mark.unit
def test_cli_rejects_an_unapproved_manifest_before_creating_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    raw = _raw_manifest()
    raw["approved_by_owner"] = False
    path = tmp_path / "unapproved.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-game-pilot",
            str(path),
            "--owner-approved",
            "--execute-approved-manifest",
        ],
    )

    assert result.exit_code != 0
    assert "approved_by_owner must be true" in result.output
    assert created == []


@pytest.mark.unit
def test_cli_rejects_a_fast_rate_before_creating_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "12")

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-game-pilot",
            str(_write_manifest(tmp_path)),
            "--owner-approved",
            "--execute-approved-manifest",
        ],
    )

    assert result.exit_code != 0
    assert "10 requests/minute" in result.output
    assert created == []


@pytest.mark.unit
def test_cli_acquires_through_a_client_that_stops_on_the_first_429(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "10")
    instances: list[FakePilotClient] = []
    retries: list[int] = []

    class CliClient(FakePilotClient):
        def __init__(self, settings: object, *, max_429_retries: int) -> None:
            super().__init__()
            retries.append(max_429_retries)
            instances.append(self)

        def __enter__(self) -> CliClient:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", CliClient)
    output = tmp_path / "reports" / "pilot.json"

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-game-pilot",
            str(_write_manifest(tmp_path)),
            "--owner-approved",
            "--execute-approved-manifest",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert retries == [0]
    assert [url for url, _ in instances[0].calls] == [SCHEDULE_URL, BOX_URL, PBP_URL]
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["fetched"] == 3
    assert written["live_request_count"] == 3
    assert HtmlCache(tmp_path / "cache").get(PBP_URL) == PAGE


@pytest.mark.unit
def test_cli_writes_the_partial_report_and_exits_1_when_the_run_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "10")

    class StoppingClient(FakePilotClient):
        def __init__(self, settings: object, *, max_429_retries: int) -> None:
            super().__init__(rate_limit_on=BOX_URL)

        def __enter__(self) -> StoppingClient:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", StoppingClient)
    output = tmp_path / "reports" / "partial.json"

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-game-pilot",
            str(_write_manifest(tmp_path)),
            "--owner-approved",
            "--execute-approved-manifest",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["stopped_reason"] == "rate_limited"
    assert written["stopped_at_entry"] == 2


@pytest.mark.unit
def test_cli_dry_run_never_creates_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))

    result = CliRunner().invoke(
        app,
        ["acquisition", "dry-run-game-pilot", str(_write_manifest(tmp_path))],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["estimated_fetch_count"] == 3
    assert created == []
