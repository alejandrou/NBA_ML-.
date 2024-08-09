from scrap.scrap_team import TeamScraper
from db_manager.db_operations import DBOperations
from models.team import Team
from models.player import Player
from scrap.scrap_player import PlayerScraper
from utils.team_name_abbrev import team_abbrev

def main():
    db_ops = DBOperations()
    print("Connecting to database...")
    db_ops.connect_db()
    
    
    scraper_team = TeamScraper()
    print("Creating team table...")
    team_df = scraper_team.get_team_table()
    db_ops.create_tables(Team)
    

    print("Inserting teams...")
    for index, row in team_df.iterrows():
        team_name = row['Team']
        Team.create(
            team_name=team_name,
            team_abbreviation=team_abbrev.get(team_name, None),
            league=row['Lg'],
            from_year=row['From'],
            to_year=row['To'],
            years=row['Yrs'],
            games=row['G'],
            wins=row['W'],
            losses=row['L'],
            win_loss_percentage=row['W/L%'],
            playoffs=row['Plyfs'],
            division=row['Div'],
            conference=row['Conf'],
            championships=row['Champ']
        )
    
    
    scraper_player = PlayerScraper()
    print("Creating player table...")
    player_dict = scraper_player.get_players_team_year()
    db_ops.create_tables(Player)
    
    
    print("Inserting players...")
    
   # Invertir el diccionario para mapear las abreviaturas a los nombres completos
    abbrev_to_team = {v: k for k, v in team_abbrev.items()}

    # Asumiendo que `player_dict` tiene las abreviaturas de los equipos
    for team_abbreviation, years_data in player_dict.items():
    # Convertir la abreviatura al nombre completo del equipo
        team_name = abbrev_to_team.get(team_abbreviation)

    # Asegurarse de que el equipo exista en el mapeo
        if team_name:
        # Obtener la instancia del equipo de la base de datos
            team_instance = Team.get(Team.team_name == team_name)
            
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
                            'player_experience': row['Exp'],
                            'player_college': row['College'],
                            'player_team': team_name,
                            'player_year_in_team': year,
                            'id_team': team_instance.team_id  # Relacionar con el equipo
                        }
                        Player.create(**player_data)
        else:
            print(f"No se encontró el equipo para la abreviatura {team_abbreviation}")
        
    
    # db_ops.drop_tables(Team)
    print("Closing database connection...")
    db_ops.close_db()

    
if __name__ == "__main__":
    main()