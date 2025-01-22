from db_manager.db_manager import DBManager
from db_manager.team_operations.team_operations import TeamOperations
from db_manager.player_operations import PlayerOperations
import asyncio
import httpx


async def main():
    data_manager = DBManager()
    player_operations = PlayerOperations()
    team_operations = TeamOperations()

    print("Connecting to database...")
    data_manager.connect_db()

    print("Creating schemas...")
    data_manager.create_schemas('teams')
    data_manager.create_schemas('players')

    print("Creating team table and inserting data...")
    # team_operations.insert_teams()
    async with httpx.AsyncClient() as client:
        print("Scraping and saving team season results...")
        await team_operations.get_regular_season_results_data(client)
        # print("Scraping and saving player rosters...")
        # await player_operations.scrape_and_save_players_roster_async(client)
        # print("Scraping and saving player totals...")
        # await player_operations.scrape_and_save_players_totals_async(client)
        # print("Scraping and saving player advanced...")
        # await player_operations.scrape_and_save_players_advanced(client)
 
    #To do
    #Normalize database -> 
        #Problems with normalize:
            #table team_season gets wins and losses of the team the whole lifetime not just that year, needs fix. Fixed
            #win loss percentage does that too, i think, fix. Fixed
            #there will be a problem with duplicate data that maybe it will need to have a implementation of squema teams -> team: ATL -> team_ATL_season. But we will see
        #normalize players

    #Check class db_operations.py - nvm doesnt do anything, just deleted it :check:
    #calculate time of one year
    #add injury table
    #put years inside the method to scrape from command line
    
    # print("Creating player table and inserting data...")
    # await player_operations.scrape_and_save_players_roster()
    # await player_operations.scrape_and_save_players_advanced()

    # print("Dropping schemas...")
    # data_manager.drop_schemas('teams')
    # data_manager.drop_schemas('players')
    
    print("Closing database connection...")
    data_manager.close_db()

if __name__ == "__main__":
    asyncio.run(main())