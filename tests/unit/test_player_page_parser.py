from pathlib import Path

import pytest

from nba_data.scraping.parsers.player_page import (
    SUPPORTED_PLAYER_PAGE_REGULAR_SEASON_TABLES,
    parse_player_page_regular_season,
)

FIXTURE = Path("tests/fixtures/html/player_page_harden_regular_season.html")


@pytest.mark.unit
def test_parse_player_page_regular_season_reads_supported_visible_and_commented_tables() -> None:
    parsed = parse_player_page_regular_season(FIXTURE.read_text(encoding="utf-8"))

    assert set(parsed) == set(SUPPORTED_PLAYER_PAGE_REGULAR_SEASON_TABLES)
    assert [row["team_id"] for row in parsed["totals"]] == ["2TM", "HOU", "BRK"]
    assert parsed["per_game"][0]["pts_per_g"] == "24.6"
    assert parsed["advanced"][0]["per"] == "25.0"


@pytest.mark.unit
def test_parse_player_page_regular_season_returns_empty_lists_for_missing_tables() -> None:
    parsed = parse_player_page_regular_season("<html><body></body></html>")

    assert parsed["totals"] == []
    assert parsed["per_game"] == []
    assert parsed["advanced"] == []
