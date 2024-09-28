from db_manager.db_conf import db
from scrap.scrap_team.scrap_team import TeamScraper
from scrap.scrap_team.scrap_team_regular_season_results import TeamScraperRegularSeasonResults
from scrap.scrap_player.scrap_player_roster import PlayerScraperRoster
from scrap.scrap_player.scrap_player_totals import PlayerScraperTotals
from scrap.scrap_player.scrap_player_advanced import PlayerScraperAdvanced
from models.team.team import Team
from models.team.team_regular_season_results import TeamRegularSeasonResults
from models.player.player import Player
from models.player.player_stats import PlayerStats
from models.player.player_advanced import PlayerAdvancedStats
from utils.team_name_abbrev import team_abbrev

class DBOperations():
    
        def __init__(self):
            self.scraper_team = TeamScraper()
            self.scraper_player_roster = PlayerScraperRoster()
            self.scraper_player_totals = PlayerScraperTotals()
            self.scraper_player_advanced = PlayerScraperAdvanced()
            self.scraper_team_regultar_season_results = TeamScraperRegularSeasonResults()
        
        def connect_db(self):
            db.connect()
        
        def close_db(self):
            db.close()
        
        def create_tables(self, table):
            db.create_tables([table])
            
        def drop_tables(self, table):
            db.drop_tables([table])
        
        def create_schemas(self, schema_name):
             db.execute_sql(f'CREATE SCHEMA IF NOT EXISTS {schema_name};')
             
        def drop_schemas(self, schema_name):
            db.execute_sql(f'DROP SCHEMA IF EXISTS {schema_name} CASCADE;')


################ Teams #######################
        def scrape_and_save_teams(self):
            team_data = self.scraper_team.get_team_table()
            self.create_tables(Team)
            for team in team_data:
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
                

            
        async def scrape_and_save_teams_season_results(self):
            self.create_tables(TeamRegularSeasonResults)
            team_regular_season_results = await self.scraper_team_regultar_season_results.get_team_regular_season_results()
            
                
            for team_name, years_data in team_regular_season_results.items():
                team_instance = Team.get(Team.team_abbreviation == team_name)
                for year, teams in years_data.items():
                    for team in teams:
                            team_data = {
                                'id_team': team_instance.id_team,
                                'game': team.get('g', None),
                                'date_game': team.get('date_game', None),
                                'game_start_time': team.get('game_start_time', None),
                                'network':team.get('network', None),
                                'box_score_text':team.get('box_score_text', None),
                                'game_location':team.get('game_location', None),
                                'opp_name':team.get('opp_name', None),
                                'game_result':team.get('game_result', None),
                                'overtimes':team.get('overtimes', None),
                                'pts':team.get('pts', None),
                                'opp_pts':team.get('opp_pts', None),
                                'wins':team.get('wins', None),
                                'losses':team.get('losses', None),
                                'game_streak':team.get('game_streak', None),
                                'attendance':team.get('attendance', None),
                                'game_duration':team.get('game_duration', None),
                                'game_remarks':team.get('game_remarks', None),
                                'year': year
                            }
                            TeamRegularSeasonResults.create(**team_data)

################ Players #######################       
        async def scrape_and_save_players_roster(self):
            self.create_tables(Player)
            player_roster = await self.scraper_player_roster.get_players_team_year_roster()

            for team_name, years_data in player_roster.items():
                team_instance = Team.get(Team.team_abbreviation == team_name)
                for year, players_data in years_data.items():
                    for player in players_data:
                        player_data = {
                            'number_player': player.get('No.', None),
                            'id_team': team_instance.id_team,
                            'player_name': player.get('Player', None),
                            'player_position': player.get('Pos', None),
                            'player_height': player.get('Ht', None),
                            'player_weight': player.get('Wt', None),
                            'player_birth_date': player.get('Birth Date', None),
                            'player_experience': player.get('Exp', None),
                            'player_college': player.get('College', None),
                            'player_team': team_name,
                            'player_year_in_team': year,
                        }
                        Player.create(**player_data)
                        
        
        async def scrape_and_save_players_totals(self):
            self.create_tables(PlayerStats)
            player_totals = await self.scraper_player_totals.get_players_team_year_totals()

            for nba_team, years_data in player_totals.items():
                for year, players_data in years_data.items():
                    for player in players_data:
                        # Intenta obtener la instancia del jugador por nombre y equipo
                        try:
                            player_instance = Player.get(
                                (Player.player_name == player['Player'])
                            )
                        except Player.DoesNotExist:
                            print(f"Player {player['Player']} not found for {nba_team} in {year}. Skipping...")
                            continue
                        
                        #Si se encuentra el jugador, crea el registro en PlayerStats
                        player_data = {
                            'id_player': player_instance.id_player,  # Clave foránea de Player
                            'player': player.get('Player', None),
                            'age' : player.get('Age', None),
                            'games' : player.get('G', None),
                            'games_started' : player.get('GS', None),
                            'minutes_played' : player.get('MP', None),
                            'field_goals' : player.get('FG', None),
                            'field_goals_attempted' : player.get('FGA', None),
                            'field_goals_percentage' : player.get('FG%', None),
                            'three_point_field_goals' : player.get('3P', None),
                            'three_point_field_goals_attempted' : player.get('3PA', None),
                            'three_point_field_goals_percentage' : player.get('3P%', None),
                            'two_point_field_goals' : player.get('2P', None),
                            'two_point_field_goals_attempted' : player.get('2PA', None),
                            'two_point_field_goals_percentage' : player.get('2P%', None),
                            'effective_field_goals_percentage' : player.get('eFG%', None),
                            'free_throws' : player.get('FT', None),
                            'free_throws_attempted' : player.get('FTA', None),
                            'free_throws_percentage' : player.get('FT%', None),
                            'offensive_rebounds' : player.get('ORB', None),
                            'defensive_rebounds' : player.get('DRB', None),
                            'total_rebounds' : player.get('TRB', None),
                            'assists' : player.get('AST', None),
                            'steals' : player.get('STL', None),
                            'blocks' : player.get('BLK', None),
                            'turnovers' : player.get('TOV', None),
                            'personal_fouls' : player.get('PF', None),
                            'points' : player.get('PTS', None),
                        }
                        PlayerStats.create(**player_data)


        async def scrape_and_save_players_advanced(self):
            self.create_tables(PlayerAdvancedStats)
            player_advanced = await self.scraper_player_advanced.get_players_team_year_advanced()

            for nba_team, years_data in player_advanced.items():
                for year, players_data in years_data.items():
                    for player in players_data:
                        # Intenta obtener la instancia del jugador por nombre y equipo
                            try:
                                player_instance = Player.get(
                                    (Player.player_name == player['Player'])
                                )
                            except Player.DoesNotExist:
                                print(f"Player {player['Player']} not found for {nba_team} in {year}. Skipping...")
                                continue
                            
                            #Si se encuentra el jugador, crea el registro en PlayerAdvancedStats
                            player_data = {
                                'id_player': player_instance.id_player,  # Clave foránea de Player
                                'rk' : player.get('Rk', None),
                                'player' : player.get('Player', None),
                                'age' : player.get('Age', None),
                                'games' : player.get('G', None),
                                'minutes_played' : player.get('MP', None),
                                'player_effiencey_rating' : player.get('PER', None),
                                'true_shooting_percentage' : player.get('TS%', None),
                                'three_point_attempt_rate' : player.get('3PAr', None),
                                'free_throw_attempt_rate' : player.get('FTr', None),
                                'offensive_rebound_percentage' : player.get('ORB%', None),
                                'defensive_rebound_percentage' : player.get('DRB%', None),
                                'total_rebound_percentage' : player.get('TRB%', None),
                                'assist_percentage' : player.get('AST%', None),
                                'steal_percentage' : player.get('STL%', None),
                                'block_percentage' : player.get('BLK%', None),
                                'turnover_percentage' : player.get('TOV%', None),
                                'usage_percentage' : player.get('USG%', None),
                                'offensive_win_shares' : player.get('OWS', None),
                                'defensive_win_shares' : player.get('DWS', None),
                                'win_shares' : player.get('WS', None),
                                'win_shares_per_48_minutes' : player.get('WS/48', None),
                                'offensive_box_plus_minus' : player.get('OBPM', None),
                                'defensive_box_plus_minus' : player.get('DBPM', None),
                                'box_plus_minus' : player.get('BPM', None),
                                'value_over_replacement_player' : player.get('VORP', None),
                            }
                            PlayerAdvancedStats.create(**player_data)
                    
                       
        

