from __future__ import annotations

import inspect
import json
import re
from urllib.parse import urlparse

import pytest
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.scraping import nba_team_season_manifest
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.nba_team_season_manifest import (
    EXPECTED_MANIFEST_URLS,
    build_nba_team_season_dry_run_report,
    build_nba_team_season_manifest,
)

BOS_2024_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
DEN_2023_URL = "https://www.basketball-reference.com/teams/DEN/2023.html"
TEAM_SEASON_URL_RE = re.compile(
    r"^https://www\.basketball-reference\.com/teams/[A-Z]{3}/[0-9]{4}\.html$"
)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


def _teams_by_year() -> dict[int, set[str]]:
    manifest = build_nba_team_season_manifest()
    teams: dict[int, set[str]] = {}
    for entry in manifest.entries:
        teams.setdefault(entry.season_end_year, set()).add(entry.team)
    return teams


@pytest.mark.unit
def test_manifest_contains_exactly_775_unique_team_season_urls() -> None:
    manifest = build_nba_team_season_manifest()
    urls = [entry.url for entry in manifest.entries]

    assert manifest.season_start_year == 2000
    assert manifest.season_end_year == 2025
    assert manifest.total_urls == EXPECTED_MANIFEST_URLS
    assert manifest.unique_urls == EXPECTED_MANIFEST_URLS
    assert len(manifest.entries) == EXPECTED_MANIFEST_URLS
    assert len(set(urls)) == EXPECTED_MANIFEST_URLS


@pytest.mark.unit
def test_manifest_urls_are_only_basketball_reference_team_season_pages() -> None:
    manifest = build_nba_team_season_manifest()

    for entry in manifest.entries:
        parsed = urlparse(entry.url)
        assert entry.page_type == "team_season"
        assert TEAM_SEASON_URL_RE.fullmatch(entry.url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "www.basketball-reference.com"
        assert parsed.query == ""
        assert parsed.fragment == ""
        assert "_games" not in parsed.path
        assert "/players/" not in parsed.path
        assert "/boxscores/" not in parsed.path


@pytest.mark.unit
def test_manifest_uses_phase_4d_franchise_lineage_boundaries() -> None:
    teams = _teams_by_year()

    assert "VAN" in teams[2000]
    assert "VAN" in teams[2001]
    assert "MEM" not in teams[2001]
    assert "MEM" in teams[2002]

    assert "CHH" in teams[2002]
    assert "NOH" in teams[2003]
    assert "NOH" in teams[2005]
    assert "NOK" in teams[2006]
    assert "NOK" in teams[2007]
    assert "NOH" in teams[2008]
    assert "NOH" in teams[2013]
    assert "NOP" in teams[2014]

    assert "CHA" not in teams[2004]
    assert "CHA" in teams[2005]
    assert "CHA" in teams[2014]
    assert "CHO" in teams[2015]

    assert "NJN" in teams[2012]
    assert "BRK" in teams[2013]

    assert "SEA" in teams[2008]
    assert "OKC" in teams[2009]


@pytest.mark.unit
def test_dry_run_reports_cache_hits_missing_entries_and_zero_unsupported_counts(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "html-cache")
    cache.set(BOS_2024_URL, "<html>cached bos</html>")
    cache.set(DEN_2023_URL, "<html>cached den</html>")

    report = build_nba_team_season_dry_run_report(cache=cache)
    report_data = report.to_dict()

    assert report_data["total_urls"] == EXPECTED_MANIFEST_URLS
    assert report_data["unique_urls"] == EXPECTED_MANIFEST_URLS
    assert report_data["cache_hits"] == 2
    assert report_data["missing_cache_entries"] == EXPECTED_MANIFEST_URLS - 2
    assert report_data["estimated_fetch_count"] == EXPECTED_MANIFEST_URLS - 2
    assert report_data["skipped_entries"] == 0
    assert report_data["unsupported_entries"] == 0

    entries = report_data["entries"]
    assert isinstance(entries, list)
    entries_by_url = {entry["url"]: entry for entry in entries}
    assert entries_by_url[BOS_2024_URL]["cache_status"] == "hit"
    assert entries_by_url[BOS_2024_URL]["estimated_fetch_count"] == 0
    assert entries_by_url[DEN_2023_URL]["cache_status"] == "hit"
    assert entries_by_url[DEN_2023_URL]["cache_path"].endswith(".html.gz")


@pytest.mark.unit
def test_dry_run_does_not_accept_network_client() -> None:
    signature = inspect.signature(build_nba_team_season_dry_run_report)

    assert "client" not in signature.parameters


@pytest.mark.unit
def test_manifest_module_does_not_import_network_parser_loader_or_db_boundaries() -> None:
    source = inspect.getsource(nba_team_season_manifest)

    assert "BasketballReferenceClient" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert "parse_" not in source
    assert "load_" not in source
    assert "Session" not in source


@pytest.mark.unit
def test_cli_acquisition_dry_run_nba_team_seasons_prints_json_report(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(tmp_path / "html-cache"))
    get_settings.cache_clear()
    cache = HtmlCache(tmp_path / "html-cache")
    cache.set(BOS_2024_URL, "<html>cached bos</html>")

    result = CliRunner().invoke(app, ["acquisition", "dry-run-nba-team-seasons"])

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["manifest_id"] == "nba-team-season-2000-2025"
    assert report["total_urls"] == EXPECTED_MANIFEST_URLS
    assert report["unique_urls"] == EXPECTED_MANIFEST_URLS
    assert report["cache_hits"] == 1
    assert report["missing_cache_entries"] == EXPECTED_MANIFEST_URLS - 1
    assert report["estimated_fetch_count"] == EXPECTED_MANIFEST_URLS - 1
