import asyncio
from db_manager.db_operations import DBOperations

async def main():
    data_manager = DBOperations()

    print("Connecting to database...")
    data_manager.connect_db()

    print("Creating team table and inserting data...")
    data_manager.scrape_and_save_teams()

    print("Creating player table and inserting data...")
    await data_manager.scrape_and_save_players()

    print("Closing database connection...")
    data_manager.close_db()

if __name__ == "__main__":
    asyncio.run(main())