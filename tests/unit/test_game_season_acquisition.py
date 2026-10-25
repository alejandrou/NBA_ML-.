from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.config.settings import MINIMUM_SCRAPER_DELAY_SECONDS, Settings, get_settings
from nba_data.scraping.cache import CacheFetchMetadata, HtmlCache
from nba_data.scraping.cache_inventory import build_cached_html_inventory
from nba_data.scraping.client import (
    BasketballReferenceClient,
    FetchResult,
    RateLimitExceededError,
    RequestBudgetExhaustedError,
)
from nba_data.scraping.game_season_acquisition import (
    PLACEHOLDER_USER_AGENT,
    GameSeasonAcquisitionConfigurationError,
    GameSeasonAcquisitionStopped,
    acquire_game_season_manifest,
    build_game_season_dry_run_report,
    validate_game_season_acquisition_settings,
    validate_settings_within_manifest_policy,
)
from nba_data.scraping.game_season_manifest import (
    GameSeasonManifest,
    validate_game_season_manifest,
)

BASE = "https://www.basketball-reference.com"
GAME_IDS = ("202310240DEN", "202310250NYK", "202312090LAL", "202404140IND")
URLS = tuple(f"{BASE}/boxscores/{game_id}.html" for game_id in GAME_IDS)
SCHEDULE_URL = f"{BASE}/leagues/NBA_2024_games-may.html"
FETCHED_AT = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
PAGE = "<!DOCTYPE html><html><body>page</body></html>"
TEST_USER_AGENT = "nba-data-tests/0.1 contact:tests@nba-data.invalid"


def _raw_manifest(*, approved: bool = True, requests_per_minute: int = 10) -> dict[str, Any]:
    return {
        "manifest_id": "F8-004-test",
        "status": "approved" if approved else "draft",
        "approved_by_owner": approved,
        "approved_at": "2026-10-25T12:00:00Z" if approved else None,
        "approval_basis": "Test fixture approval." if approved else None,
        "scope": {"season_end_year": 2024, "page_type": "box_score", "max_urls": len(GAME_IDS)},
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
                "page_type": "box_score",
                "url": url,
                "season_end_year": 2024,
                "game_id": game_id,
                "reason": "Regular-season game.",
            }
            for game_id, url in zip(GAME_IDS, URLS, strict=True)
        ],
    }


def _manifest(**kwargs: Any) -> GameSeasonManifest:
    return validate_game_season_manifest(_raw_manifest(**kwargs), require_approval=False)


def _write_manifest(tmp_path: Path, **kwargs: Any) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_raw_manifest(**kwargs)), encoding="utf-8")
    return path


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "scraper_user_agent": TEST_USER_AGENT,
        "scraper_max_requests_per_minute": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakeSeasonClient:
    """Counts requests and honours a budget the way the real client does.

    Each fetch costs 7 fake seconds; `retries_on` makes one URL take two attempts.
    """

    def __init__(
        self,
        *,
        fail_on: str | None = None,
        rate_limit_on: str | None = None,
        retries_on: str | None = None,
        max_requests: int | None = None,
    ) -> None:
        self.clock = FakeClock()
        self.fail_on = fail_on
        self.rate_limit_on = rate_limit_on
        self.retries_on = retries_on
        self.max_requests = max_requests
        self.calls: list[str] = []
        self._request_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    def fetch(self, url: str, *, force_refresh: bool = False) -> FetchResult:
        assert force_refresh is False
        self.calls.append(url)
        for _attempt in range(2 if url == self.retries_on else 1):
            if self.max_requests is not None and self._request_count >= self.max_requests:
                msg = f"planned budget exhausted before {url}"
                raise RequestBudgetExhaustedError(msg)
            self._request_count += 1
        self.clock.now += 7.0
        if url == self.rate_limit_on:
            msg = f"planned rate limit for {url}"
            raise RateLimitExceededError(msg)
        if url == self.fail_on:
            msg = f"planned failure for {url}"
            raise RuntimeError(msg)
        metadata = CacheFetchMetadata(fetched_at=FETCHED_AT, http_status=200, final_url=url)
        return FetchResult(html=PAGE, metadata=metadata)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


def _acquire(
    cache: HtmlCache,
    client: FakeSeasonClient,
    *,
    max_fetches: int | None = None,
) -> Any:
    return acquire_game_season_manifest(
        _manifest(), cache=cache, client=client, max_fetches=max_fetches, clock=client.clock
    )


@pytest.mark.unit
def test_dry_run_reports_hits_misses_and_the_minimum_duration_even_for_a_draft(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(URLS[0], PAGE)

    report = build_game_season_dry_run_report(
        _manifest(approved=False), cache=cache, settings=_settings()
    )

    assert report.status == "draft"
    assert report.total_entries == 4
    assert report.cache_hits == 1
    assert report.estimated_fetch_count == 3
    assert report.estimated_minimum_seconds == 2 * MINIMUM_SCRAPER_DELAY_SECONDS
    assert [entry.cache_status for entry in report.entries] == [
        "hit",
        "missing",
        "missing",
        "missing",
    ]


@pytest.mark.unit
def test_a_draft_is_never_acquired(tmp_path: Path) -> None:
    client = FakeSeasonClient()

    with pytest.raises(GameSeasonAcquisitionConfigurationError, match="approved"):
        acquire_game_season_manifest(
            _manifest(approved=False), cache=HtmlCache(tmp_path), client=client
        )

    assert client.calls == []


@pytest.mark.unit
def test_cache_hits_cost_nothing_and_are_never_overwritten(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    for url in URLS:
        cache.set(url, "<html>cached</html>")
    client = FakeSeasonClient()

    report = _acquire(cache, client, max_fetches=1)

    assert client.calls == []
    assert report.completed is True
    assert report.cache_hits == 4
    assert report.live_request_count == 0
    assert cache.get(URLS[0]) == "<html>cached</html>"


@pytest.mark.unit
def test_misses_are_fetched_once_written_with_provenance_and_measured(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(URLS[0], PAGE)
    client = FakeSeasonClient()

    report = _acquire(cache, client)

    assert client.calls == list(URLS[1:])
    assert report.completed is True
    assert report.stopped_reason is None
    assert report.fetched == 3
    assert report.live_request_count == 3
    assert report.wall_seconds == 21.0
    assert report.fetched_bytes == 3 * len(PAGE.encode("utf-8"))
    entry = report.entries[1]
    assert entry.status == "fetched"
    assert entry.game_id == GAME_IDS[1]
    assert entry.http_status == 200
    assert entry.fetched_at == FETCHED_AT.isoformat()
    assert entry.compressed_bytes == Path(entry.cache_path).stat().st_size
    assert entry.elapsed_seconds == 7.0
    assert cache.get_metadata(URLS[1]) == CacheFetchMetadata(
        fetched_at=FETCHED_AT, http_status=200, final_url=URLS[1]
    )


@pytest.mark.unit
def test_max_fetches_stops_cleanly_and_a_rerun_resumes_from_the_cache(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(URLS[1], PAGE)
    first = FakeSeasonClient()

    report = _acquire(cache, first, max_fetches=2)

    assert first.calls == [URLS[0], URLS[2]]
    assert report.completed is False
    assert report.stopped_reason == "max_fetches"
    assert report.stopped_at_entry == 4
    assert report.processed_entries == 3
    assert report.remaining_entries == 1
    assert report.cache_hits == 1
    assert report.live_request_count == 2
    assert report.max_fetches == 2
    assert not cache.exists(URLS[3])

    second = FakeSeasonClient()
    resumed = _acquire(cache, second, max_fetches=2)

    assert second.calls == [URLS[3]]
    assert resumed.completed is True
    assert resumed.cache_hits == 3
    assert resumed.live_request_count == 1


@pytest.mark.unit
def test_max_fetches_counts_retried_requests(tmp_path: Path) -> None:
    client = FakeSeasonClient(retries_on=URLS[0], max_requests=2)

    report = _acquire(HtmlCache(tmp_path), client, max_fetches=2)

    assert client.calls == [URLS[0]]
    assert report.live_request_count == 2
    assert report.stopped_reason == "max_fetches"
    assert report.stopped_at_entry == 2


@pytest.mark.unit
def test_a_retry_past_the_budget_stops_cleanly_and_leaves_the_page_uncached(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path)
    client = FakeSeasonClient(retries_on=URLS[0], max_requests=1)

    report = _acquire(cache, client, max_fetches=1)

    assert report.live_request_count == 1
    assert report.completed is False
    assert report.stopped_reason == "max_fetches"
    assert report.stopped_at_entry == 1
    assert report.entries[0].status == "max_fetches"
    assert report.remaining_entries == 4
    assert not cache.exists(URLS[0])


@pytest.mark.unit
def test_the_real_client_never_sends_a_5xx_retry_past_max_fetches(tmp_path: Path) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(500, text="server error")

    client = BasketballReferenceClient(
        _settings(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=lambda _: None,
        max_requests=1,
    )
    cache = HtmlCache(tmp_path)

    report = acquire_game_season_manifest(_manifest(), cache=cache, client=client, max_fetches=1)

    assert requested == [URLS[0]]
    assert client.request_count == 1
    assert report.live_request_count == 1
    assert report.stopped_reason == "max_fetches"
    assert not cache.exists(URLS[0])


@pytest.mark.unit
def test_dry_run_estimates_at_the_slower_of_the_configured_and_approved_pace(
    tmp_path: Path,
) -> None:
    report = build_game_season_dry_run_report(
        _manifest(requests_per_minute=1), cache=HtmlCache(tmp_path), settings=_settings()
    )

    assert report.estimated_fetch_count == 4
    assert report.estimated_minimum_seconds == 180.0


@pytest.mark.unit
@pytest.mark.parametrize("status_code", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("max_fetches", [None, 1])
def test_redirects_stop_before_an_unapproved_request_and_leave_no_cached_page(
    tmp_path: Path, status_code: int, max_fetches: int | None
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if len(requested) == 1:
            return httpx.Response(status_code, headers={"Location": "https://example.org/page"})
        return httpx.Response(200, text=PAGE)

    cache = HtmlCache(tmp_path)
    with (
        httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as http,
        BasketballReferenceClient(
            _settings(), http_client=http, max_requests=max_fetches, follow_redirects=False
        ) as client,
    ):
        with pytest.raises(GameSeasonAcquisitionStopped) as raised:
            acquire_game_season_manifest(
                _manifest(), cache=cache, client=client, max_fetches=max_fetches
            )

        assert client.request_count == 1

    report = raised.value.report
    assert requested == [URLS[0]]
    assert report.live_request_count == 1
    assert report.stopped_reason == "failed"
    assert report.remaining_entries == len(URLS)
    assert report.fetched == 0
    assert not cache.exists(URLS[0])
    assert not cache.metadata_path_for_url(URLS[0]).exists()


@pytest.mark.unit
def test_max_fetches_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(GameSeasonAcquisitionConfigurationError, match="at least 1"):
        _acquire(HtmlCache(tmp_path), FakeSeasonClient(), max_fetches=0)


@pytest.mark.unit
def test_a_429_stops_the_run_with_a_partial_report(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    client = FakeSeasonClient(rate_limit_on=URLS[1])

    with pytest.raises(GameSeasonAcquisitionStopped) as raised:
        _acquire(cache, client, max_fetches=10)

    report = raised.value.report
    assert client.calls == [URLS[0], URLS[1]]
    assert report.completed is False
    assert report.stopped_reason == "rate_limited"
    assert report.stopped_at_entry == 2
    assert report.rate_limited == 1
    assert report.live_request_count == 2
    assert report.entries[1].error_details == f"planned rate limit for {URLS[1]}"
    assert not cache.exists(URLS[1])


@pytest.mark.unit
def test_any_other_failure_stops_the_run_with_a_partial_report(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    client = FakeSeasonClient(fail_on=URLS[2])

    with pytest.raises(GameSeasonAcquisitionStopped) as raised:
        _acquire(cache, client)

    report = raised.value.report
    assert report.stopped_reason == "failed"
    assert report.stopped_at_entry == 3
    assert report.fetched == 2
    assert report.failures == 1
    assert not cache.exists(URLS[2])
    assert not cache.exists(URLS[3])


@pytest.mark.unit
def test_acquired_game_pages_stay_unsupported_paths_to_the_cache_inventory(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    _acquire(cache, FakeSeasonClient())
    cache.set(SCHEDULE_URL, PAGE)

    inventory = build_cached_html_inventory(cache=cache)

    assert inventory.total_discovered_files == 5
    assert {entry.status for entry in inventory.entries} == {"unsupported_path"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "user_agent",
    [PLACEHOLDER_USER_AGENT, "nba-data-project/0.1 contact:someone@EXAMPLE.com"],
)
def test_the_placeholder_user_agent_is_refused(user_agent: str) -> None:
    with pytest.raises(GameSeasonAcquisitionConfigurationError, match="placeholder"):
        validate_game_season_acquisition_settings(_settings(scraper_user_agent=user_agent))


@pytest.mark.unit
def test_settings_above_ten_requests_per_minute_are_refused() -> None:
    with pytest.raises(GameSeasonAcquisitionConfigurationError, match="10 requests/minute"):
        validate_game_season_acquisition_settings(_settings(scraper_max_requests_per_minute=11))
    validate_game_season_acquisition_settings(_settings())


@pytest.mark.unit
def test_settings_faster_than_the_manifest_approves_are_refused() -> None:
    manifest = _manifest(requests_per_minute=6)

    with pytest.raises(GameSeasonAcquisitionConfigurationError, match="the manifest approves"):
        validate_settings_within_manifest_policy(_settings(), manifest)
    validate_settings_within_manifest_policy(_settings(scraper_max_requests_per_minute=6), manifest)


def _forbid_client_creation(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    created: list[object] = []

    class ForbiddenClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created.append(self)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", ForbiddenClient)
    return created


def _cli_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "10")
    monkeypatch.setenv("SCRAPER_USER_AGENT", TEST_USER_AGENT)


def _flat(output: str) -> str:
    """CLI output with the error panel's borders and line wrapping removed."""

    return " ".join(re.sub(r"[─-╿|]", " ", output).split())


def _acquire_args(path: Path, *extra: str) -> list[str]:
    return [
        "acquisition",
        "acquire-game-season",
        str(path),
        "--owner-approved",
        "--execute-approved-manifest",
        *extra,
    ]


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
        "nba_data.cli.main.load_game_season_manifest",
        lambda path, **kwargs: read.append(path),
    )

    result = CliRunner().invoke(
        app,
        ["acquisition", "acquire-game-season", str(tmp_path / "absent.json"), *flags],
    )

    assert result.exit_code == 1
    assert "Refusing acquisition without --owner-approved and --execute-approved-manifest" in (
        result.output
    )
    assert read == []
    assert created == []


@pytest.mark.unit
def test_cli_refuses_the_placeholder_user_agent_before_creating_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    _cli_env(monkeypatch, tmp_path)
    monkeypatch.setenv("SCRAPER_USER_AGENT", PLACEHOLDER_USER_AGENT)

    result = CliRunner().invoke(app, _acquire_args(_write_manifest(tmp_path)))

    assert result.exit_code != 0
    assert "placeholder" in _flat(result.output)
    assert created == []


@pytest.mark.unit
def test_cli_refuses_a_draft_manifest_before_creating_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    _cli_env(monkeypatch, tmp_path)

    result = CliRunner().invoke(app, _acquire_args(_write_manifest(tmp_path, approved=False)))

    assert result.exit_code != 0
    assert "status must be 'approved'" in _flat(result.output)
    assert created == []


@pytest.mark.unit
def test_cli_refuses_a_fast_rate_before_creating_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    _cli_env(monkeypatch, tmp_path)
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "12")

    result = CliRunner().invoke(app, _acquire_args(_write_manifest(tmp_path)))

    assert result.exit_code != 0
    assert "10 requests/minute" in _flat(result.output)
    assert created == []


@pytest.mark.unit
def test_cli_rejects_a_max_fetches_below_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    _cli_env(monkeypatch, tmp_path)

    result = CliRunner().invoke(app, _acquire_args(_write_manifest(tmp_path), "--max-fetches", "0"))

    assert result.exit_code == 2
    assert created == []


def _cli_client_class(
    instances: list[FakeSeasonClient],
    retries: list[int],
    **client_kwargs: Any,
) -> type[FakeSeasonClient]:
    class CliClient(FakeSeasonClient):
        def __init__(
            self,
            settings: object,
            *,
            max_429_retries: int,
            max_requests: int | None,
            follow_redirects: bool,
        ) -> None:
            assert follow_redirects is False
            super().__init__(max_requests=max_requests, **client_kwargs)
            retries.append(max_429_retries)
            instances.append(self)

        def __enter__(self) -> CliClient:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

    return CliClient


@pytest.mark.unit
def test_cli_batches_with_max_fetches_and_exits_0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    instances: list[FakeSeasonClient] = []
    retries: list[int] = []
    monkeypatch.setattr(
        "nba_data.cli.main.BasketballReferenceClient", _cli_client_class(instances, retries)
    )
    manifest_path = _write_manifest(tmp_path)
    output = tmp_path / "reports" / "batch-1.json"

    result = CliRunner().invoke(
        app, _acquire_args(manifest_path, "--max-fetches", "3", "--output", str(output))
    )

    assert result.exit_code == 0, result.output
    assert retries == [0]
    assert instances[0].max_requests == 3
    assert instances[0].calls == list(URLS[:3])
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["stopped_reason"] == "max_fetches"
    assert written["live_request_count"] == 3
    assert written["remaining_entries"] == 1

    result = CliRunner().invoke(app, _acquire_args(manifest_path, "--max-fetches", "3"))

    assert result.exit_code == 0, result.output
    assert instances[1].calls == [URLS[3]]
    assert json.loads(result.output)["completed"] is True


@pytest.mark.unit
def test_cli_writes_the_partial_report_and_exits_1_on_a_429(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _cli_env(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "nba_data.cli.main.BasketballReferenceClient",
        _cli_client_class([], [], rate_limit_on=URLS[1]),
    )
    output = tmp_path / "reports" / "partial.json"

    result = CliRunner().invoke(
        app, _acquire_args(_write_manifest(tmp_path), "--output", str(output))
    )

    assert result.exit_code == 1
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["stopped_reason"] == "rate_limited"
    assert written["stopped_at_entry"] == 2


@pytest.mark.unit
def test_cli_dry_run_reads_a_draft_and_never_creates_a_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    _cli_env(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        app,
        ["acquisition", "dry-run-game-season", str(_write_manifest(tmp_path, approved=False))],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["estimated_fetch_count"] == 4
    assert created == []


@pytest.mark.unit
def test_cli_plans_write_drafts_offline_and_never_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _forbid_client_creation(monkeypatch)
    _cli_env(monkeypatch, tmp_path)
    draft = tmp_path / "reports" / "schedules.json"
    args = ["acquisition", "plan-game-schedules", "--season", "2024", "--output", str(draft)]

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 0, result.output
    written = json.loads(draft.read_text(encoding="utf-8"))
    assert written["status"] == "draft"
    assert [entry["url"] for entry in written["entries"]] == [f"{BASE}/leagues/NBA_2024_games.html"]

    again = CliRunner().invoke(app, args)
    assert again.exit_code != 0
    assert "already exists" in _flat(again.output)

    box_scores = CliRunner().invoke(
        app, ["acquisition", "plan-game-box-scores", "--season", "2024", "--output", str(draft)]
    )
    assert box_scores.exit_code != 0
    assert "plan and acquire the schedules first" in _flat(box_scores.output)
    assert created == []
    assert not (tmp_path / "cache").exists()
