from scrap.scrap_team import TeamScraper
from db_manager.db_operations import DBOperations
from models.team import Team

def main():
    scraper = TeamScraper('https://www.basketball-reference.com/teams/')
    db_ops = DBOperations()

    print("Connecting to database...")
    db_ops.connect_db()

    # print("Creating tables...")
    # team_df = scraper.get_team_table()
    # db_ops.create_tables(Team)
    
    # print("Inserting data...")
    # for index, row in team_df.iterrows():
    #     Team.create(
    #         team=row['Team'],
    #         league=row['Lg'],
    #         from_year=row['From'],
    #         to_year=row['To'],
    #         years=row['Yrs'],
    #         games=row['G'],
    #         wins=row['W'],
    #         losses=row['L'],
    #         win_loss_percentage=row['W/L%'],
    #         playoffs=row['Plyfs'],
    #         division=row['Div'],
    #         conference=row['Conf'],
    #         championships=row['Champ']
    #     )
    
    print("Closing database connection...")
    db_ops.close_db()

    
if __name__ == "__main__":
    main()