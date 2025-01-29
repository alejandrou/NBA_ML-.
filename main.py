from db_manager.db_manager import DBManager
from db_manager.team_operations.team_operations import TeamOperations
from db_manager.player_operations.player_operations import PlayerOperations
import asyncio
import httpx
import sys

def parse_years():
    if len(sys.argv) == 1:
        return [2024]
    return [int(year) for year in sys.argv[1:]]  

async def main():
    years = parse_years()
    data_manager = DBManager()
    player_operations = PlayerOperations(years)
    team_operations = TeamOperations(years)

    data_manager.connect_db()
    data_manager.create_schemas('teams')
    data_manager.create_schemas('players')

    print("Creating team table and inserting data...")
    async with httpx.AsyncClient() as client:
        print("Scraping and saving team season results...")
        await team_operations.get_regular_season_results_data(client)
        print("Scraping and saving player rosters...")
        await player_operations.scrape_and_save_players_roster_async(client)
        print("Scraping and saving player totals...")
        await player_operations.scrape_and_save_players_totals_async(client)
        print("Scraping and saving player advanced...")
        await player_operations.scrape_and_save_players_advanced(client)

    print("Closing database connection...")
    data_manager.close_db()

if __name__ == "__main__":
    asyncio.run(main())