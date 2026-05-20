"""Normalize parsed Basketball Reference rows into canonical records."""

from nba_data.scraping.normalizers.team_season import normalize_team_season_page

__all__ = ["normalize_team_season_page"]
