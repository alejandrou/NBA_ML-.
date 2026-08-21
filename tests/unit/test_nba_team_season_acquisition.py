from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.scraping import nba_team_season_acquisition as acquisition
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import RateLimitExceededError
from nba_data.scraping.nba_team_season_acquisition import (
    NbaTeamSeasonAcquisitionConfigurationError,
    NbaTeamSeasonAcquisitionStopped,
    _write_html_to_cache_safely,
    acquire_nba_team_season_manifest,
    build_verified_nba_team_season_acquisition_manifest,
    validate_phase_4d_acquisition_settings,
)
from nba_data.scraping.nba_team_season_manifest import (
    EXPECTED_MANIFEST_URLS,
    MANIFEST_ID,
    NbaTeamSeasonManifest,
    NbaTeamSeasonManifestEntry,
)

BOS_2024_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
DEN_2023_URL = "https://www.basketball-reference.com/teams/DEN/2023.html"


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
            msg = f"planned rate limit for {url}"
            raise RateLimitExceededError(msg)
        if url == self.fail_on:
            msg = f"planned failure for {url}"
            raise RuntimeError(msg)
        return self.html


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


def _entry(team: str, season_end_year: int) -> NbaTeamSeasonManifestEntry:
    return NbaTeamSeasonManifestEntry(
        page_type="team_season",
        team=team,
        season_end_year=season_end_year,
        url=f"https://www.basketball-reference.com/teams/{team}/{season_end_year}.html",
    )


def _manifest(*entries: NbaTeamSeasonManifestEntry) -> NbaTeamSeasonManifest:
    return NbaTeamSeasonManifest(
        manifest_id=MANIFEST_ID,
        season_start_year=2000,
        season_end_year=2025,
        total_urls=len(entries),
        unique_urls=len({entry.url for entry in entries}),
        entries=tuple(entries),
    )


def _allow_small_manifest(monkeypatch: pytest.MonkeyPatch, manifest: NbaTeamSeasonManifest) -> None:
    monkeypatch.setattr(acquisition, "EXPECTED_MANIFEST_URLS", len(manifest.entries))


@pytest.mark.unit
def test_verified_manifest_uses_expected_id_and_775_entries() -> None:
    manifest = build_verified_nba_team_season_acquisition_manifest()

    assert manifest.manifest_id == "nba-team-season-2000-2025"
    assert len(manifest.entries) == EXPECTED_MANIFEST_URLS
    assert manifest.total_urls == EXPECTED_MANIFEST_URLS
    assert manifest.unique_urls == EXPECTED_MANIFEST_URLS


@pytest.mark.unit
def test_filtered_manifest_uses_requested_year_range() -> None:
    manifest = build_verified_nba_team_season_acquisition_manifest(
        start_year=2020,
        end_year=2025,
    )

    assert manifest.manifest_id == "nba-team-season-2000-2025"
    assert manifest.season_start_year == 2020
    assert manifest.season_end_year == 2025
    assert manifest.total_urls == 180
    assert manifest.unique_urls == 180
    assert {entry.season_end_year for entry in manifest.entries} == {
        2020,
        2021,
        2022,
        2023,
        2024,
        2025,
    }

    earlier_manifest = build_verified_nba_team_season_acquisition_manifest(
        start_year=2015,
        end_year=2020,
    )
    assert earlier_manifest.total_urls == 180
    assert {entry.season_end_year for entry in earlier_manifest.entries} == {
        2015,
        2016,
        2017,
        2018,
        2019,
        2020,
    }


@pytest.mark.unit
def test_filtered_manifest_rejects_ranges_outside_reviewed_catalog() -> None:
    with pytest.raises(NbaTeamSeasonAcquisitionConfigurationError, match="2000-2025"):
        build_verified_nba_team_season_acquisition_manifest(start_year=1990, end_year=2025)

    with pytest.raises(NbaTeamSeasonAcquisitionConfigurationError, match="2000-2025"):
        build_verified_nba_team_season_acquisition_manifest(start_year=2000, end_year=2026)

    with pytest.raises(NbaTeamSeasonAcquisitionConfigurationError, match="less than or equal"):
        build_verified_nba_team_season_acquisition_manifest(start_year=2025, end_year=2020)


@pytest.mark.unit
def test_manifest_validation_happens_before_client_call(tmp_path) -> None:
    manifest = NbaTeamSeasonManifest(
        manifest_id="wrong-manifest",
        season_start_year=2024,
        season_end_year=2024,
        total_urls=1,
        unique_urls=1,
        entries=(_entry("BOS", 2024),),
    )
    cache = HtmlCache(tmp_path / "cache")
    client = FakeAcquisitionClient()

    with pytest.raises(NbaTeamSeasonAcquisitionConfigurationError, match="Expected manifest_id"):
        acquire_nba_team_season_manifest(manifest, cache=cache, client=client)

    assert client.calls == []


@pytest.mark.unit
def test_cache_hit_does_not_call_client_or_overwrite_existing_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(_entry("BOS", 2024))
    _allow_small_manifest(monkeypatch, manifest)
    cache = HtmlCache(tmp_path / "cache")
    cache.set(BOS_2024_URL, "<html>cached</html>")
    client = FakeAcquisitionClient("<html>fresh</html>")

    report = acquire_nba_team_season_manifest(manifest, cache=cache, client=client)

    assert client.calls == []
    assert cache.get(BOS_2024_URL) == "<html>cached</html>"
    assert report.cache_hits == 1
    assert report.fetched == 0
    assert report.live_request_count == 0
    assert report.entries[0].status == "cache_hit"


@pytest.mark.unit
def test_cache_miss_fetches_once_validates_and_writes_html(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(_entry("BOS", 2024))
    _allow_small_manifest(monkeypatch, manifest)
    cache = HtmlCache(tmp_path / "cache")
    client = FakeAcquisitionClient("<!doctype html><html>fresh</html>")

    report = acquire_nba_team_season_manifest(manifest, cache=cache, client=client)
    report_data = report.to_dict()

    assert client.calls == [(BOS_2024_URL, False)]
    assert cache.get(BOS_2024_URL) == "<!doctype html><html>fresh</html>"
    assert report_data["manifest_id"] == MANIFEST_ID
    assert report_data["total_urls"] == 1
    assert report_data["processed_entries"] == 1
    assert report_data["fetched"] == 1
    assert report_data["completed"] is True
    assert report_data["stopped_reason"] is None
    assert report_data["stopped_at_entry"] is None

    entry = report_data["entries"][0]
    assert set(entry) == {
        "index",
        "team",
        "season_end_year",
        "url",
        "cache_path",
        "status",
        "error_details",
    }
    assert entry["index"] == 1
    assert entry["team"] == "BOS"
    assert entry["season_end_year"] == 2024
    assert entry["url"] == BOS_2024_URL
    assert entry["cache_path"].endswith(".html.gz")
    assert entry["status"] == "fetched"
    assert entry["error_details"] is None


@pytest.mark.unit
def test_invalid_fetched_content_stops_before_cache_write(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(_entry("BOS", 2024))
    _allow_small_manifest(monkeypatch, manifest)
    cache = HtmlCache(tmp_path / "cache")
    client = FakeAcquisitionClient("not html")

    with pytest.raises(NbaTeamSeasonAcquisitionStopped) as exc_info:
        acquire_nba_team_season_manifest(manifest, cache=cache, client=client)

    assert cache.get(BOS_2024_URL) is None
    report = exc_info.value.report
    assert report.completed is False
    assert report.failed == 1
    assert report.stopped_reason == "failed"
    assert report.stopped_at_entry == 1
    assert report.entries[0].status == "failed"
    assert "HTML document" in (report.entries[0].error_details or "")


@pytest.mark.unit
def test_safe_cache_write_failure_leaves_no_partial_final_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    final_path = cache.path_for_url(BOS_2024_URL)

    def fail_replace(source: Path, target: Path) -> None:
        msg = f"planned replace failure for {target}"
        raise OSError(msg)

    monkeypatch.setattr(acquisition.os, "replace", fail_replace)

    with pytest.raises(OSError, match="planned replace failure"):
        _write_html_to_cache_safely(cache, BOS_2024_URL, "<html>fresh</html>")

    assert not final_path.exists()
    assert list(final_path.parent.glob(f".{final_path.name}.*.tmp")) == []


@pytest.mark.unit
def test_safe_cache_write_preserves_crlf_html_for_verification(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    html = "<!doctype html>\r\n<html>\r\n<body>fresh</body>\r\n</html>"

    final_path = _write_html_to_cache_safely(cache, BOS_2024_URL, html)

    with gzip.open(final_path, "rt", encoding="utf-8", newline="") as file:
        assert file.read() == html


@pytest.mark.unit
def test_generic_fetch_failure_stops_with_partial_report(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(_entry("BOS", 2024), _entry("DEN", 2023))
    _allow_small_manifest(monkeypatch, manifest)
    cache = HtmlCache(tmp_path / "cache")
    cache.set(BOS_2024_URL, "<html>cached</html>")
    client = FakeAcquisitionClient(fail_on=DEN_2023_URL)

    with pytest.raises(NbaTeamSeasonAcquisitionStopped) as exc_info:
        acquire_nba_team_season_manifest(manifest, cache=cache, client=client)

    report = exc_info.value.report
    assert client.calls == [(DEN_2023_URL, False)]
    assert report.processed_entries == 2
    assert report.cache_hits == 1
    assert report.failed == 1
    assert report.rate_limited == 0
    assert report.live_request_count == 1
    assert report.completed is False
    assert report.stopped_reason == "failed"
    assert report.stopped_at_entry == 2
    assert [entry.status for entry in report.entries] == ["cache_hit", "failed"]
    assert "planned failure" in (report.entries[1].error_details or "")


@pytest.mark.unit
def test_rate_limit_failure_stops_with_partial_report_without_slow_sleep(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(_entry("BOS", 2024), _entry("DEN", 2023))
    _allow_small_manifest(monkeypatch, manifest)
    cache = HtmlCache(tmp_path / "cache")
    cache.set(BOS_2024_URL, "<html>cached</html>")
    client = FakeAcquisitionClient(rate_limit_on=DEN_2023_URL)

    with pytest.raises(NbaTeamSeasonAcquisitionStopped) as exc_info:
        acquire_nba_team_season_manifest(manifest, cache=cache, client=client)

    report = exc_info.value.report
    assert client.calls == [(DEN_2023_URL, False)]
    assert report.processed_entries == 2
    assert report.cache_hits == 1
    assert report.failed == 0
    assert report.rate_limited == 1
    assert report.live_request_count == 1
    assert report.completed is False
    assert report.stopped_reason == "rate_limited"
    assert report.stopped_at_entry == 2
    assert [entry.status for entry in report.entries] == ["cache_hit", "rate_limited"]
    assert "planned rate limit" in (report.entries[1].error_details or "")


@pytest.mark.unit
def test_phase_4d_command_rejects_rate_limit_above_12(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPER_MAX_REQUESTS_PER_MINUTE", "13")
    get_settings.cache_clear()

    with pytest.raises(NbaTeamSeasonAcquisitionConfigurationError, match="12 requests/minute"):
        validate_phase_4d_acquisition_settings(get_settings())


@pytest.mark.unit
def test_cli_refuses_without_approval_flags_before_client_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_clients: list[object] = []

    class FakeBasketballReferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created_clients.append(self)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", FakeBasketballReferenceClient)

    result = CliRunner().invoke(app, ["acquisition", "acquire-nba-team-seasons", "2020", "2025"])

    assert result.exit_code != 0
    assert "Refusing acquisition" in result.output
    assert created_clients == []


@pytest.mark.unit
def test_cli_validates_manifest_before_client_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    created_clients: list[object] = []

    class FakeBasketballReferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created_clients.append(self)

    def fail_manifest(*, start_year: int, end_year: int) -> NbaTeamSeasonManifest:
        assert start_year == 2020
        assert end_year == 2025
        msg = "planned manifest validation failure"
        raise NbaTeamSeasonAcquisitionConfigurationError(msg)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", FakeBasketballReferenceClient)
    monkeypatch.setattr(
        "nba_data.cli.main.build_verified_nba_team_season_acquisition_manifest",
        fail_manifest,
    )

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-nba-team-seasons",
            "2020",
            "2025",
            "--owner-approved",
            "--execute-approved-manifest",
        ],
    )

    assert result.exit_code != 0
    assert "planned manifest validation failure" in result.output
    assert created_clients == []


@pytest.mark.unit
def test_cli_missing_years_fails_before_client_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    created_clients: list[object] = []

    class FakeBasketballReferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created_clients.append(self)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", FakeBasketballReferenceClient)

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-nba-team-seasons",
            "--owner-approved",
            "--execute-approved-manifest",
        ],
    )

    assert result.exit_code != 0
    assert created_clients == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("start_year", "end_year", "expected_message"),
    [
        ("1990", "2025", "2000-2025"),
        ("2000", "2026", "2000-2025"),
        ("2025", "2020", "less than or equal"),
    ],
)
def test_cli_invalid_year_ranges_fail_before_client_creation(
    start_year: str,
    end_year: str,
    expected_message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_clients: list[object] = []

    class FakeBasketballReferenceClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created_clients.append(self)

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", FakeBasketballReferenceClient)

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-nba-team-seasons",
            start_year,
            end_year,
            "--owner-approved",
            "--execute-approved-manifest",
        ],
    )

    assert result.exit_code != 0
    assert expected_message in result.output
    assert created_clients == []


@pytest.mark.unit
def test_cli_acquire_uses_fake_basketball_reference_client_only(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _manifest(_entry("BOS", 2024))
    _allow_small_manifest(monkeypatch, manifest)
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    fake_instances: list[FakeAcquisitionClient] = []

    class FakeBasketballReferenceClient(FakeAcquisitionClient):
        def __init__(self, settings: object, *, max_429_retries: int) -> None:
            super().__init__("<html>cli fresh</html>")
            self.settings = settings
            self.max_429_retries = max_429_retries
            fake_instances.append(self)

        def __enter__(self) -> FakeBasketballReferenceClient:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    def build_manifest(*, start_year: int, end_year: int) -> NbaTeamSeasonManifest:
        assert start_year == 2024
        assert end_year == 2024
        return manifest

    monkeypatch.setattr(
        "nba_data.cli.main.build_verified_nba_team_season_acquisition_manifest",
        build_manifest,
    )
    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", FakeBasketballReferenceClient)
    output_path = tmp_path / "reports" / "acquisition-2024-2024.json"

    result = CliRunner().invoke(
        app,
        [
            "acquisition",
            "acquire-nba-team-seasons",
            "2024",
            "2024",
            "--owner-approved",
            "--execute-approved-manifest",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(fake_instances) == 1
    assert fake_instances[0].max_429_retries == 0
    assert fake_instances[0].calls == [(BOS_2024_URL, False)]
    summary = json.loads(result.output)
    written_report = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["fetched"] == 1
    assert summary["live_request_count"] == 1
    assert summary["output_path"] == str(output_path.resolve())
    assert written_report["fetched"] == 1
    assert written_report["live_request_count"] == 1
    assert summary["entries"] == len(written_report["entries"])
    assert HtmlCache(tmp_path / "cache").get(BOS_2024_URL) == "<html>cli fresh</html>"
