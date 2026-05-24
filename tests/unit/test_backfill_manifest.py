from __future__ import annotations

import inspect
import json
from copy import deepcopy
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.scraping.backfill_manifest import (
    BackfillAcquisitionError,
    ManifestValidationError,
    dry_run_backfill_manifest,
    run_backfill_acquisition,
    validate_backfill_manifest,
)
from nba_data.scraping.cache import HtmlCache

MANIFEST = Path("tests/fixtures/manifests/approved_team_season_manifest.json")
BOS_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
DEN_URL = "https://www.basketball-reference.com/teams/DEN/2023.html"


def _manifest_data() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _write_manifest(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class FakeBackfillClient:
    def __init__(self, html: str = "<html>network</html>", fail_on: str | None = None) -> None:
        self.html = html
        self.fail_on = fail_on
        self.calls: list[tuple[str, bool]] = []

    def get(self, url: str, *, force_refresh: bool = False) -> str:
        self.calls.append((url, force_refresh))
        if url == self.fail_on:
            msg = f"planned failure for {url}"
            raise RuntimeError(msg)
        return self.html


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.mark.unit
def test_dry_run_reports_cache_paths_and_estimated_live_request_count(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>cached</html>")

    report = dry_run_backfill_manifest(MANIFEST, cache=cache)
    report_data = report.to_dict()

    assert report_data["manifest_id"] == "pilot-team-season-20260524"
    assert report_data["total_entries"] == 2
    assert report_data["cache_hits"] == 1
    assert report_data["cache_misses"] == 1
    assert report_data["estimated_live_request_count"] == 1

    entries = report_data["entries"]
    assert isinstance(entries, list)
    assert entries[0]["url"] == BOS_URL
    assert entries[0]["cache_status"] == "hit"
    assert entries[0]["estimated_live_request_count"] == 0
    assert str(entries[0]["cache_path"]).endswith(".html.gz")
    assert entries[1]["url"] == DEN_URL
    assert entries[1]["cache_status"] == "miss"
    assert entries[1]["estimated_live_request_count"] == 1


@pytest.mark.unit
def test_acquisition_requires_approved_manifest(tmp_path) -> None:
    data = _manifest_data()
    data["status"] = "draft"
    manifest_path = _write_manifest(tmp_path, data)
    cache = HtmlCache(tmp_path / "cache")
    client = FakeBackfillClient()

    with pytest.raises(ManifestValidationError, match="status must be 'approved'"):
        run_backfill_acquisition(manifest_path, cache=cache, client=client)

    assert client.calls == []


@pytest.mark.unit
def test_acquisition_cache_hit_makes_no_client_request(tmp_path) -> None:
    data = _manifest_data()
    data["entries"] = [data["entries"][0]]
    manifest_path = _write_manifest(tmp_path, data)
    cache = HtmlCache(tmp_path / "cache")
    cache.set(BOS_URL, "<html>cached</html>")
    client = FakeBackfillClient()

    report = run_backfill_acquisition(manifest_path, cache=cache, client=client)

    assert client.calls == []
    assert report.cache_hits == 1
    assert report.fetched == 0
    assert report.live_request_count == 0
    assert report.entries[0].status == "cache_hit"


@pytest.mark.unit
def test_acquisition_cache_miss_fetches_once_and_stores_html(tmp_path) -> None:
    data = _manifest_data()
    data["entries"] = [data["entries"][0]]
    manifest_path = _write_manifest(tmp_path, data)
    cache = HtmlCache(tmp_path / "cache")
    client = FakeBackfillClient("<html>fresh</html>")

    report = run_backfill_acquisition(manifest_path, cache=cache, client=client)

    assert client.calls == [(BOS_URL, False)]
    assert cache.get(BOS_URL) == "<html>fresh</html>"
    assert report.cache_hits == 0
    assert report.fetched == 1
    assert report.live_request_count == 1
    assert report.entries[0].status == "fetched"
    assert report.entries[0].cache_path.endswith(".html.gz")


@pytest.mark.unit
def test_acquisition_processes_entries_sequentially(tmp_path) -> None:
    manifest_path = _write_manifest(tmp_path, _manifest_data())
    cache = HtmlCache(tmp_path / "cache")
    client = FakeBackfillClient()

    report = run_backfill_acquisition(manifest_path, cache=cache, client=client)

    assert client.calls == [(BOS_URL, False), (DEN_URL, False)]
    assert [entry.url for entry in report.entries] == [BOS_URL, DEN_URL]
    assert [entry.status for entry in report.entries] == ["fetched", "fetched"]
    assert report.processed_entries == 2
    assert report.live_request_count == 2


@pytest.mark.unit
def test_acquisition_failure_stops_with_partial_report(tmp_path) -> None:
    manifest_path = _write_manifest(tmp_path, _manifest_data())
    cache = HtmlCache(tmp_path / "cache")
    cache.set(BOS_URL, "<html>cached</html>")
    client = FakeBackfillClient(fail_on=DEN_URL)

    with pytest.raises(BackfillAcquisitionError) as exc_info:
        run_backfill_acquisition(manifest_path, cache=cache, client=client)

    assert client.calls == [(DEN_URL, False)]
    report = exc_info.value.report
    assert report.total_entries == 2
    assert report.processed_entries == 2
    assert report.cache_hits == 1
    assert report.fetched == 0
    assert report.failures == 1
    assert report.live_request_count == 1
    assert [entry.status for entry in report.entries] == ["cache_hit", "failed"]
    assert "planned failure" in (report.entries[1].error_message or "")


@pytest.mark.unit
def test_manifest_validation_requires_owner_approval() -> None:
    data = _manifest_data()
    data["status"] = "draft"
    data["approved_by_owner"] = False

    with pytest.raises(ManifestValidationError, match="status must be 'approved'"):
        validate_backfill_manifest(data)


@pytest.mark.unit
def test_manifest_validation_rejects_duplicate_urls() -> None:
    data = _manifest_data()
    entries = data["entries"]
    assert isinstance(entries, list)
    entries.append(deepcopy(entries[0]))

    with pytest.raises(ManifestValidationError, match="duplicates"):
        validate_backfill_manifest(data)


@pytest.mark.unit
def test_manifest_validation_rejects_unsupported_urls() -> None:
    data = _manifest_data()
    entries = data["entries"]
    assert isinstance(entries, list)
    entry = entries[0]
    assert isinstance(entry, dict)
    entry["url"] = "https://www.basketball-reference.com/players/t/tatumja01.html"

    with pytest.raises(ManifestValidationError, match="team-season URL"):
        validate_backfill_manifest(data)


@pytest.mark.unit
def test_manifest_validation_rejects_unsafe_acquisition_policy() -> None:
    data = _manifest_data()
    policy = data["acquisition_policy"]
    assert isinstance(policy, dict)
    policy["cache_first"] = False

    with pytest.raises(ManifestValidationError, match="cache_first must be true"):
        validate_backfill_manifest(data)

    data = _manifest_data()
    policy = data["acquisition_policy"]
    assert isinstance(policy, dict)
    policy["requests_per_minute"] = 11

    with pytest.raises(ManifestValidationError, match="between 1 and 10"):
        validate_backfill_manifest(data)


@pytest.mark.unit
def test_manifest_validation_rejects_more_than_five_urls() -> None:
    data = _manifest_data()
    entries = data["entries"]
    assert isinstance(entries, list)
    first_entry = entries[0]
    assert isinstance(first_entry, dict)
    for offset in range(4):
        next_entry = deepcopy(first_entry)
        next_entry["url"] = f"https://www.basketball-reference.com/teams/NYK/202{offset}.html"
        next_entry["team"] = "NYK"
        next_entry["season_end_year"] = 2020 + offset
        entries.append(next_entry)

    with pytest.raises(ManifestValidationError, match="exceeds scope.max_urls"):
        validate_backfill_manifest(data)


@pytest.mark.unit
def test_dry_run_does_not_accept_network_client() -> None:
    signature = inspect.signature(dry_run_backfill_manifest)

    assert "client" not in signature.parameters


@pytest.mark.unit
def test_cli_backfill_dry_run_prints_json_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "html-cache"))
    get_settings.cache_clear()
    cache = HtmlCache(tmp_path / "html-cache")
    cache.set(BOS_URL, "<html>cached</html>")

    result = CliRunner().invoke(app, ["backfill", "dry-run", str(MANIFEST)])

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["manifest_id"] == "pilot-team-season-20260524"
    assert report["cache_hits"] == 1
    assert report["cache_misses"] == 1
    assert report["estimated_live_request_count"] == 1


@pytest.mark.unit
def test_cli_backfill_acquire_refuses_without_explicit_flag(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["backfill", "acquire", str(MANIFEST)])

    assert result.exit_code != 0
    assert "Refusing acquisition" in result.output


@pytest.mark.unit
def test_cli_backfill_acquire_uses_fake_client_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "html-cache"))
    get_settings.cache_clear()

    fake_instances: list[FakeBackfillClient] = []

    class FakeBasketballReferenceClient(FakeBackfillClient):
        def __init__(self, settings: object) -> None:
            super().__init__("<html>cli fresh</html>")
            fake_instances.append(self)

        def __enter__(self) -> FakeBasketballReferenceClient:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    monkeypatch.setattr("nba_data.cli.main.BasketballReferenceClient", FakeBasketballReferenceClient)

    result = CliRunner().invoke(
        app,
        ["backfill", "acquire", str(MANIFEST), "--execute-approved-manifest"],
    )

    assert result.exit_code == 0, result.output
    assert len(fake_instances) == 1
    assert fake_instances[0].calls == [(BOS_URL, False), (DEN_URL, False)]
    cache = HtmlCache(tmp_path / "html-cache")
    assert cache.get(BOS_URL) == "<html>cli fresh</html>"
    report = json.loads(result.output)
    assert report["fetched"] == 2
    assert report["live_request_count"] == 2
