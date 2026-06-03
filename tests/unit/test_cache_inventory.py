import gzip
import inspect
from pathlib import Path

import pytest

import nba_data.scraping.cache_inventory as cache_inventory
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import build_cached_html_inventory

BOS_2024_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
DEN_2023_URL = "https://www.basketball-reference.com/teams/DEN/2023.html"
VALID_HTML = "<!doctype html><html><body>cached</body></html>"


@pytest.mark.unit
def test_inventory_discovers_valid_team_season_cache_entry(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    cache_path = cache.path_for_url(BOS_2024_URL)
    _write_gzip(cache_path, VALID_HTML)

    inventory = build_cached_html_inventory(cache=cache)
    inventory_data = inventory.to_dict()

    assert inventory.total_discovered_files == 1
    assert inventory.valid_candidates == 1
    assert inventory.invalid_or_unreadable_files == 0
    assert inventory.duplicate_candidates == 0
    assert inventory.missing_metadata == 0
    assert inventory.unsupported_paths == 0
    assert inventory_data["cache_root"] == str(cache.root_dir.resolve(strict=False))

    entry = inventory.entries[0]
    assert entry.status == "valid"
    assert entry.cache_path == str(cache_path)
    assert entry.source_url == BOS_2024_URL
    assert entry.is_basketball_reference is True
    assert entry.team_abbreviation == "BOS"
    assert entry.season_year == 2024
    assert entry.season_end_year == 2024
    assert entry.page_type == "team_season"
    assert entry.error_message is None
    assert inventory_data["entries"][0] == entry.to_dict()


@pytest.mark.unit
def test_inventory_marks_duplicate_team_season_candidates_after_first_valid(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    first = (
        cache.root_dir
        / "basketball-reference"
        / "teams-bos-2024.html-1111111111111111.html.gz"
    )
    second = (
        cache.root_dir
        / "basketball-reference"
        / "teams-bos-2024.html-2222222222222222.html.gz"
    )
    _write_gzip(first, VALID_HTML)
    _write_gzip(second, VALID_HTML)

    inventory = build_cached_html_inventory(cache=cache)

    assert [entry.status for entry in inventory.entries] == ["valid", "duplicate"]
    assert inventory.valid_candidates == 1
    assert inventory.duplicate_candidates == 1
    assert inventory.entries[1].source_url == BOS_2024_URL
    assert inventory.entries[1].team_abbreviation == "BOS"


@pytest.mark.unit
def test_inventory_marks_unsupported_hosts_pages_catalog_entries_and_tot(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    paths = [
        cache.root_dir
        / "example.com"
        / "teams-bos-2024.html-1111111111111111.html.gz",
        cache.root_dir
        / "basketball-reference"
        / "players-t-tatumja01.html-2222222222222222.html.gz",
        cache.root_dir
        / "basketball-reference"
        / "teams-bos-2026.html-3333333333333333.html.gz",
        cache.root_dir
        / "basketball-reference"
        / "teams-tot-2024.html-4444444444444444.html.gz",
    ]
    for path in paths:
        _write_gzip(path, VALID_HTML)

    inventory = build_cached_html_inventory(cache=cache)

    assert inventory.total_discovered_files == 4
    assert inventory.unsupported_paths == 4
    assert {entry.status for entry in inventory.entries} == {"unsupported_path"}

    player_entry = next(entry for entry in inventory.entries if "players-t" in entry.cache_path)
    assert player_entry.is_basketball_reference is True
    assert player_entry.page_type is None

    out_of_catalog_entry = next(
        entry for entry in inventory.entries if entry.season_end_year == 2026
    )
    assert out_of_catalog_entry.team_abbreviation == "BOS"
    assert "outside the approved" in str(out_of_catalog_entry.error_message)

    external_entry = next(entry for entry in inventory.entries if "example.com" in entry.cache_path)
    assert external_entry.is_basketball_reference is False

    tot_entry = next(entry for entry in inventory.entries if entry.team_abbreviation == "TOT")
    assert "aggregate marker" in str(tot_entry.error_message)


@pytest.mark.unit
def test_inventory_marks_basketball_reference_team_season_like_missing_metadata(
    tmp_path,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    path = (
        cache.root_dir
        / "basketball-reference"
        / "teams-bos.html-1111111111111111.html.gz"
    )
    _write_gzip(path, VALID_HTML)

    inventory = build_cached_html_inventory(cache=cache)

    assert inventory.total_discovered_files == 1
    assert inventory.missing_metadata == 1
    entry = inventory.entries[0]
    assert entry.status == "missing_metadata"
    assert entry.is_basketball_reference is True
    assert entry.source_url is None
    assert entry.team_abbreviation is None
    assert "missing team or season metadata" in str(entry.error_message)


@pytest.mark.unit
def test_inventory_marks_unreadable_or_non_html_gzip_as_invalid(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    malformed = cache.path_for_url(BOS_2024_URL)
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_bytes(b"not a gzip payload")
    non_html = cache.path_for_url(DEN_2023_URL)
    _write_gzip(non_html, "plain text")

    inventory = build_cached_html_inventory(cache=cache)

    assert inventory.total_discovered_files == 2
    assert inventory.invalid_or_unreadable_files == 2
    assert {entry.status for entry in inventory.entries} == {"invalid_or_unreadable"}
    assert {entry.team_abbreviation for entry in inventory.entries} == {"BOS", "DEN"}


@pytest.mark.unit
def test_inventory_rejects_discovered_paths_that_resolve_outside_cache_root(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = HtmlCache(tmp_path / "cache")
    outside = (
        tmp_path
        / "outside"
        / "basketball-reference"
        / "teams-bos-2024.html-1111111111111111.html.gz"
    )
    _write_gzip(outside, VALID_HTML)

    def fake_discover(cache_root: Path) -> tuple[Path, ...]:
        assert cache_root == cache.root_dir
        return (outside,)

    def fail_if_read(path: Path) -> str:
        raise AssertionError(f"escaped path must not be read: {path}")

    monkeypatch.setattr(cache_inventory, "_discover_cached_html_files", fake_discover)
    monkeypatch.setattr(cache_inventory, "_read_html_gzip", fail_if_read)

    inventory = build_cached_html_inventory(cache=cache)

    assert inventory.total_discovered_files == 1
    assert inventory.unsupported_paths == 1
    entry = inventory.entries[0]
    assert entry.status == "unsupported_path"
    assert entry.cache_path == str(outside)
    assert "outside the cache root" in str(entry.error_message)


@pytest.mark.unit
def test_inventory_returns_empty_report_when_cache_root_is_missing(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "missing")

    inventory = build_cached_html_inventory(cache=cache)

    assert inventory.total_discovered_files == 0
    assert inventory.entries == ()
    assert inventory.valid_candidates == 0
    assert inventory.to_dict()["entries"] == []


@pytest.mark.unit
def test_cache_inventory_does_not_accept_or_import_network_parser_loader_or_db_boundaries() -> None:
    signature = inspect.signature(build_cached_html_inventory)
    module_source = inspect.getsource(cache_inventory)

    assert "client" not in signature.parameters
    assert "BasketballReferenceClient" not in module_source
    assert "requests" not in module_source
    assert "httpx" not in module_source
    assert "parse_" not in module_source
    assert "load_" not in module_source
    assert "Session" not in module_source
    assert "cache.set" not in module_source


def _write_gzip(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)
