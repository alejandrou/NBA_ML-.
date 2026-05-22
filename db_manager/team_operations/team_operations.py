from scrap.scrap_team.scrap_team import TeamScraper
from scrap.scrap_team.scrap_team_regular_season_results import TeamScraperRegularSeasonResults
from models.team.team import Team
from models.team.team_regular_season_results import TeamRegularSeasonResults
from models.team.team_season import TeamSeason
from utils.team_name_abbrev import team_abbrev, team_abbrev_old
from db_manager.db_manager import DBManager
from utils.helpers import get_win_loss_win_loss_percentage


class TeamOperations:

    def __init__(self, years, page_provider=None):
        self.page_provider = page_provider
        self.scraper_team = TeamScraper(page_provider)
        self.scraper_team_regular_season = TeamScraperRegularSeasonResults(years, page_provider)
    
    def insert_teams(self, team_data):
        DBManager.create_tables(Team)

        for team in team_data:
            team_name = team['Team']

            existing_team = Team.get_or_none(Team.team_name == team_name)
            if existing_team:
                print(f"Skipping {team_name}, already exists.")
                continue  # Skip insertion if the team exists

            Team.create(
                team_name=team_name,
                team_abbreviation=team_abbrev.get(team_name, None),
                league=team['Lg'],
                from_year=team['From'],
                to_year=team['To'],
                wins=team['W'],
                losses=team['L'],
                win_loss_percentage=team['W/L%'],
                playoffs=team['Plyfs'],
                division=team['Div'],
                conference=team['Conf'],
                championships=team['Champ']
            )
    
    def insert_old_teams(self):
        DBManager.create_tables(Team)  # Asegurar que la tabla existe

        batch_data = []
        for team_name, team_abbreviation in team_abbrev_old.items():
            print(f"Insertando equipo antiguo: {team_name}")

            if Team.get_or_none(Team.team_name == team_name):
                        print(f"Skipping {team_name}, already exists.")
                        continue  # Skip insertion if the team exists
            
            team_entry = {
                'team_name': team_name,
                'team_abbreviation': team_abbreviation,
                'league': None,
                'from_year': None,
                'to_year': None,
                'wins': None,
                'losses': None,
                'win_loss_percentage': None,
                'division': None,
                'conference': None,
                'championships': None,
            }

            batch_data.append(team_entry)

    # Insertar en lote para mayor eficiencia
        if batch_data:
            Team.insert_many(batch_data).execute()
            print("Equipos antiguos insertados correctamente.")

    async def insert_teams_season_async(self, team_regular_season_results):
        DBManager.create_tables(TeamSeason)

        batch_data = []

        for team, years_data in team_regular_season_results.items():
            team_instance = Team.get(Team.team_abbreviation == team)
            for year, stats in years_data.items():
                wins, losses, win_loss_percentage = get_win_loss_win_loss_percentage(
                    {team: {year: stats}}, team  # Pasar datos específicos del equipo y el año
                )
                base_data = {
                        'id_team': team_instance.id_team,  
                        'year': year,  # Current year as per your scraper
                        'wins': wins,
                        'losses': losses,
                        'win_loss_percentage': win_loss_percentage,
                    }

                batch_data.append(base_data)
        # Batch insert
        if batch_data:
            TeamSeason.insert_many(batch_data).execute()


    async def insert_regular_season_results_with_teams_async(self, team_regular_season_results):
        DBManager.create_tables(TeamRegularSeasonResults)
        # Crear un mapeo abreviatura -> id_team
        team_abbrev_to_id = {
            team.team_name: team.id_team for team in Team.select()}
        
        for team_abbreviation, years_data in team_regular_season_results.items():
            team_name = next((team for team, abbrev in team_abbrev.items() if abbrev == team_abbreviation), None)
            # Obtener el id_team del equipo principal
            id_team = team_abbrev_to_id.get(team_name)
            if not id_team:
                print(
                    f"Equipo con abreviatura '{team_name}' no encontrado en el diccionario. Saltando...")
                continue

            batch_data = []
            for year, games in years_data.items():
                for game in games:
                    try:
                        # Obtener el id_team del oponente
                        opp_team_name = game.get('opp_name')
                        opp_team_id = team_abbrev_to_id.get(opp_team_name)
                        if not opp_team_id:
                            print(
                                f"Equipo oponente '{game['opp_name']}' no encontrado. Usando NULL como ID.")
                            opp_team_id = None
                        
                        # Crear el diccionario para insertar
                        team_data = {
                            'opp_team': opp_team_id,  # ID numérico del oponente
                            'id_team': id_team,  # ID numérico de la temporada
                            'game': game.get('g', 0),
                            'date_game': game.get('date_game', None),
                            'game_start_time': game.get('game_start_time', None),
                            'game_location': game.get('game_location', None),
                            'opp_team': opp_team_id,  # ID numérico del oponente
                            'game_result': game.get('game_result', None),
                            'overtimes': game.get('overtimes', None),
                            'pts': game.get('pts', None),
                            'opp_pts': game.get('opp_pts', None),
                            'wins': game.get('wins', None),
                            'losses': game.get('losses', None),
                            'game_streak': game.get('game_streak', None),
                            'attendance': game.get('attendance', None),
                            'game_duration': game.get('game_duration', None),
                            'game_remarks': game.get('game_remarks', None),
                            'year': year,
                        }
                         
                        batch_data.append(team_data)
                    except KeyError as e:
                        print(f"Error al procesar los datos del juego: {e}")
                        continue
            
            # Inserción en lotes
            if batch_data:
                try:
                    TeamRegularSeasonResults.insert_many(batch_data).execute()
                    print(f"Resultados de la temporada {year} para '{team_name}' insertados.")
                except Exception as e:
                    print(f"Error al insertar los datos: {e}")


    

    async def get_regular_season_results_data(self, client=None):

        print("Iniciando scraping de datos para la temporada regular...")
        team_data = self.scraper_team.get_team_table()
        team_regular_season_results = await self.scraper_team_regular_season.get_team_regular_season_results_async()

        print("Insertando datos de la temporada regular...")
        self.insert_teams(team_data)
        self.insert_old_teams()
        await self.insert_teams_season_async(team_regular_season_results)
        await self.insert_regular_season_results_with_teams_async(team_regular_season_results)

        print("Scraping completado. Datos obtenidos para la temporada regular.")
        return team_regular_season_results
