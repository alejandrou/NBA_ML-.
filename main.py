from scrap.scrap_team import TeamScraper
from db_manager.db_operations import DBOperations
from models.team import Team
from models.player import Player
from scrap.scrap_player import PlayerScraper
def main():
    db_ops = DBOperations()
    print("Connecting to database...")
    db_ops.connect_db()
    
    
    # scraper_team = TeamScraper()
    # print("Creating team table...")
    # team_df = scraper_team.get_team_table()
    # db_ops.create_tables(Team)
    

    # print("Inserting teams...")
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
    
    


    scraper_player = PlayerScraper()
    print("Creating player table...")
    player_dict = scraper_player.get_players_team_year()
    db_ops.create_tables(Player)
    
    
    
    print("Inserting players...")
    for team, years_data in player_dict.items():
        for year, df in years_data.items():
            if not df.empty:
                for _, row in df.iterrows():
                    player_data = {
                        'team': team,
                        'year': year,
                        'player': row['Player'],
                        'pos': row['Pos'],
                        'height': row['Ht'],
                        'weight': row['Wt'],
                        'birth_date': row['Birth Date'],
                        'college': row['College'] if 'College' in row and row['College'] else None
                    }
                    Player.create(**player_data)
    
    
    # db_ops.drop_tables(Team)
    print("Closing database connection...")
    db_ops.close_db()

    
if __name__ == "__main__":
    main()