from __future__ import annotations

import gzip
import re
from pathlib import Path

import pytest

from nba_data.domain.player_id import PLAYER_ID_PATTERN
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.player_page_cache import (
    PLAYER_CACHE_FILE_RE,
    discover_player_cache_entries,
    validate_backfill_inputs,
)

PLAYER_URL = "https://www.basketball-reference.com/players/h/hardeja01.html"
MINIMAL_PLAYER_PAGE_HTML = "<html><body><div id='content'></div></body></html>"


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
def test_validate_backfill_inputs_rejects_invalid_arguments(
    kwargs: dict[str, object],
    match: str,
) -> None:
    valid_inputs: dict[str, object] = {
        "limit": None,
        "player": None,
        "start_year": None,
        "end_year": None,
        "parser_version": "player-page-parser-v4",
    }

    with pytest.raises(ValueError, match=match):
        validate_backfill_inputs(**(valid_inputs | kwargs))  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.parametrize("length", range(1, 14))
def test_cache_discovery_matches_the_shared_player_id_length_range(
    tmp_path: Path,
    length: int,
) -> None:
    player_id = "a" * (length - 1) + "1"
    filename = f"players-{player_id[0]}-{player_id}.html-{'0' * 16}.html.gz"
    cache = HtmlCache(tmp_path / "cache")
    player_url = f"https://www.basketball-reference.com/players/{player_id[0]}/{player_id}.html"
    _write_gzip(cache.path_for_url(player_url), MINIMAL_PLAYER_PAGE_HTML)

    discovered = discover_player_cache_entries(cache.root_dir, player_identifier=None)
    expected_player_ids = [player_id] if re.fullmatch(PLAYER_ID_PATTERN, player_id) else []

    assert (PLAYER_CACHE_FILE_RE.fullmatch(filename) is not None) == bool(expected_player_ids)
    assert [entry[1] for entry in discovered] == expected_player_ids


@pytest.mark.unit
def test_discovery_still_rejects_malformed_cache_filenames(tmp_path: Path) -> None:
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

    discovered = discover_player_cache_entries(cache.root_dir, player_identifier=None)

    assert [player_id for _, player_id, _ in discovered] == ["hardeja01"]


@pytest.mark.unit
def test_cache_discovery_rejects_player_ids_acquisition_cannot_write(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    _write_gzip(cache.path_for_url(PLAYER_URL), MINIMAL_PLAYER_PAGE_HTML)
    cache_dir = cache.path_for_url(PLAYER_URL).parent
    _write_gzip(
        cache_dir / "players-1-1ardeja01.html-0123456789abcdef.html.gz",
        MINIMAL_PLAYER_PAGE_HTML,
    )

    discovered = discover_player_cache_entries(cache.root_dir, player_identifier=None)

    assert [player_id for _, player_id, _ in discovered] == ["hardeja01"]


def _write_gzip(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)
