from __future__ import annotations

from types import MappingProxyType

from nba_data.scraping.parsers.team_season import _parse_table, _soup_with_commented_tables

SUPPORTED_PLAYER_PAGE_REGULAR_SEASON_TABLES = MappingProxyType(
    {
        "totals": "totals_stats",
        "per_game": "per_game_stats",
        "per_minute": "per_minute_stats",
        "per_poss": "per_poss",
        "advanced": "advanced",
        "shooting": "shooting",
        "adj_shooting": "adj_shooting",
        "pbp": "pbp_stats",
    }
)


def parse_player_page_regular_season(html: str) -> dict[str, list[dict[str, str]]]:
    """Parse supported regular-season tables from one Basketball Reference player page."""

    soup = _soup_with_commented_tables(html)
    return {
        source_table: _parse_table(soup, table_id)
        for source_table, table_id in SUPPORTED_PLAYER_PAGE_REGULAR_SEASON_TABLES.items()
    }


__all__ = [
    "SUPPORTED_PLAYER_PAGE_REGULAR_SEASON_TABLES",
    "parse_player_page_regular_season",
]
