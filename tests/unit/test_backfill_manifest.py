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
    ManifestValidationError,
    dry_run_backfill_manifest,
    validate_backfill_manifest,
)
from nba_data.scraping.cache import HtmlCache

MANIFEST = Path("tests/fixtures/manifests/approved_team_season_manifest.json")
BOS_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
DEN_URL = "https://www.basketball-reference.com/teams/DEN/2023.html"


def _manifest_data() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


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
