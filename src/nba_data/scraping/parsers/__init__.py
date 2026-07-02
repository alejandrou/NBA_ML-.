"""Pure parser functions for Basketball Reference HTML."""

from nba_data.scraping.parsers.player_page import parse_player_page_regular_season
from nba_data.scraping.parsers.team_season import parse_team_season_page

__all__ = ["parse_player_page_regular_season", "parse_team_season_page"]
