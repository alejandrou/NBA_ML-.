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

    for team in team_df:
        team_name = team['Team']
        Team.create(
            team_name=team_name,
            team_abbreviation=team_abbrev.get(team_name, None),
            league=team['Lg'],
            from_year=team['From'],
            to_year=team['To'],
            years=team['Yrs'],
            games=team['G'],
            wins=team['W'],
            losses=team['L'],
            win_loss_percentage=team['W/L%'],
            playoffs=team['Plyfs'],
            division=team['Div'],
            conference=team['Conf'],
            championships=team['Champ']
        )



    scraper_player = PlayerScraper()
    print("Creating player table...")
    db_ops.create_tables(Player)
    # Supongamos que tienes el diccionario resultante de get_players_team_year()
    players_data_by_team = scraper_player.get_players_team_year()
    
    # Ahora quieres iterar sobre este diccionario para insertar los jugadores
    for team_name, years_data in players_data_by_team.items():
        # Obtener la instancia del equipo
        team_instance = Team.get(Team.team_name == team_name)

        for year, players_data in years_data.items():
            if isinstance(players_data, list):  # Verificamos que players_data sea una lista
                for player in players_data:
                    if isinstance(player, dict):  # Verificamos que player sea un diccionario
                        player_data = {
                            'number_player': player.get('No.', None),
                            'player_name': player.get('Player', None),
                            'player_position': player.get('Pos', None),
                            'player_height': player.get('Ht', None),
                            'player_weight': player.get('Wt', None),
                            'player_birth_date': player.get('Birth Date', None),
                            'player_experience': player.get('Exp', None),
                            'player_college': player.get('College', None),
                            'player_team': team_name,
                            'player_year_in_team': year,
                            'id_team': team_instance.team_id  # Relacionar con el equipo
                        }
                        Player.create(**player_data)
                    else:
                        print(
                            f"Unexpected data type in players_data: {type(player)}")
            else:
                print(
                    f"Unexpected data type for players_data: {type(players_data)}")

    # Asumiendo que `player_dict` tiene las abreviaturas de los equipos
    # for team_abbreviation, years_data in player_dict.items():
    # # Convertir la abreviatura al nombre completo del equipo
    #     team_name = abbrev_to_team.get(team_abbreviation)

    # # Asegurarse de que el equipo exista en el mapeo
    #     if team_name:
    #     # Obtener la instancia del equipo de la base de datos
    #         team_instance = Team.get(Team.team_name == team_name)

    #         for year, df in years_data.items():
    #             if not df.empty:
    #                 for _, row in df.iterrows():
    #                     player_data = {
    #                         'number_player': row['No.'],
    #                         'player_name': row['Player'],
    #                         'player_position': row['Pos'],
    #                         'player_height': row['Ht'],
    #                         'player_weight': row['Wt'],
    #                         'player_birth_date': row['Birth Date'],
    #                         'player_experience': row['Exp'],
    #                         'player_college': row['College'],
    #                         'player_team': team_name,
    #                         'player_year_in_team': year,
    #                         'id_team': team_instance.team_id  # Relacionar con el equipo
    #                     }
    #                     Player.create(**player_data)
    #     else:
    #         print(f"No se encontró el equipo para la abreviatura {team_abbreviation}")

    # db_ops.drop_tables(Team)
    print("Closing database connection...")
    db_ops.close_db()


if __name__ == "__main__":
    main()
