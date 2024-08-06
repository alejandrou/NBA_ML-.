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
                        'number_player': row['No.'], 
                        'player_name': row['Player'],
                        'player_position': row['Pos'],
                        'player_height': row['Ht'],
                        'player_weight': row['Wt'],
                        'player_birth_date': row['Birth Date'],
                        'birth': row['Birth'],
                        'player_experience': row['Exp'],
                        'college': row['College'],
                        'player_team': team,
                        'player_year_in_team': year
                    }
                    Player.create(**player_data)
    
    
    # db_ops.drop_tables(Team)
    print("Closing database connection...")
    db_ops.close_db()

    
if __name__ == "__main__":
    main()