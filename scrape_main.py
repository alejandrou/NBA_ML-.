import asyncio
import sys

from db_manager.db_manager import DBManager
from db_manager.player_operations.player_operations import PlayerOperations
from db_manager.team_operations.team_operations import TeamOperations
from nba_data.config.settings import get_settings
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import BasketballReferenceClient
from nba_data.scraping.team_season_pages import (
    CachedBasketballReferencePageProvider,
    CachedTeamSeasonHtmlProvider,
)


def parse_years():
    if len(sys.argv) == 1:
        return [2024]
    return [int(year) for year in sys.argv[1:]]


async def main():
    years = parse_years()
    data_manager = DBManager()
    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)

    with BasketballReferenceClient(settings) as client:
        page_provider = CachedBasketballReferencePageProvider(cache=cache, client=client)
        team_season_html_provider = CachedTeamSeasonHtmlProvider(page_provider=page_provider)
        player_operations = PlayerOperations(years, team_season_html_provider)
        team_operations = TeamOperations(years, page_provider)

        data_manager.connect_db()
        data_manager.create_schemas("teams")
        data_manager.create_schemas("players")

        print("Creating team table and inserting data...")
        print("Scraping and saving team season results...")
        await team_operations.get_regular_season_results_data()
        print("Scraping and saving player rosters...")
        await player_operations.scrape_and_save_players_roster_async()
        print("Scraping and saving player totals...")
        await player_operations.scrape_and_save_players_totals_async()
        print("Scraping and saving player advanced...")
        await player_operations.scrape_and_save_players_advanced()

    print("Closing database connection...")
    data_manager.close_db()


if __name__ == "__main__":
    asyncio.run(main())
