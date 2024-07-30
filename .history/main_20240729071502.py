from scrap.scrap_team import TeamScraper
from db_manager.db_operations import DatabaseOperations

def main():
    scraper = TeamScraper('https://www.basketball-reference.com/teams/')
    db_ops = DatabaseOperations()

    # Check if the database connection is good
    if not db_ops.test_connection():
        print("Exiting due to database connection failure.")
        return

    df = scraper.get_team_table()
    db_ops.initialize_db()

    for index, row in df.iterrows():
        team_data = {
            'name': row['Franchise'],
            # Add other fields as necessary
        }
        db_ops.add_team(team_data)

if __name__ == "__main__":
    main()