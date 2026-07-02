"""Normalize parsed Basketball Reference rows into canonical records."""

from nba_data.scraping.normalizers.player_page import normalize_player_page_regular_season
from nba_data.scraping.normalizers.team_season import normalize_team_season_page

__all__ = ["normalize_player_page_regular_season", "normalize_team_season_page"]
