from scrap.scrap_team import TeamScraper
from db_manager.db_operations import DBOperations
from models.team import Team
from models.player import Player
from scrap.scrap_player import PlayerScraper
from utils.team_name_abbrev import team_abbrev

import asyncio


async def main():
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
    # players_data_by_team = scraper_player.get_players_team_year()

    # for team_name, years_data in players_data_by_team.items():
    #     team_instance = Team.get(Team.team_abbreviation == team_name)
    #     for year, players_data in years_data.items():
    #         for player in players_data:
    #             player_data = {
    #                 'number_player': player.get('No.', None),
    #                 'player_name': player.get('Player', None),
    #                 'player_position': player.get('Pos', None),
    #                 'player_height': player.get('Ht', None),
    #                 'player_weight': player.get('Wt', None),
    #                 'player_birth_date': player.get('Birth Date', None),
    #                 'player_experience': player.get('Exp', None),
    #                 'player_college': player.get('College', None),
    #                 'player_team': team_name,
    #                 'player_year_in_team': year,
    #                 'id_team': team_instance.team_id
    #             }
    #             Player.create(**player_data)

    # Ejecutar la obtención de datos
    print("Iniciando scraping...")
    teams_data = await scraper_player.get_players_team_year()

    for team_name, years_data in teams_data.items():
        team_instance = Team.get(Team.team_abbreviation == team_name)
        for year, players_data in years_data.items():
            for player in players_data:
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
                    'id_team': team_instance.team_id
                }
                Player.create(**player_data)

    # db_ops.drop_tables(Team)
    print("Closing database connection...")
    db_ops.close_db()


if __name__ == "__main__":
    asyncio.run(main())
