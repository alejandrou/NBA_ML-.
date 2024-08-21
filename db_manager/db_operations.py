from db_manager.db_conf import db
from scrap.scrap_team import TeamScraper
from scrap.scrap_player_roster import PlayerScraperRoster
from scrap.scrap_player_totals import PlayerScraperTotals
from models.team import Team
from models.player import Player
from models.player_stats import PlayerStats
from utils.team_name_abbrev import team_abbrev

class DBOperations():
    
        def __init__(self):
            self.scraper_team = TeamScraper()
            self.scraper_player_roster = PlayerScraperRoster()
            self.scraper_player_totals = PlayerScraperTotals()
        
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
        
        
        async def scrape_and_save_players_roster(self):
            self.create_tables(Player)
            player_roster = await self.scraper_player_roster.get_players_team_year_roster()

            for team_name, years_data in player_roster.items():
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
                            'id_team': team_instance.id_team
                        }
                        Player.create(**player_data)
        
        async def scrape_and_save_players_totals(self):
            self.create_tables(PlayerStats)
            player_totals = await self.scraper_player_totals.get_players_team_year_totals()

            for player_name, years_data in player_totals.items():
                for year, players_data in years_data.items():
                    for player in players_data:
                        player_instance = Player.get(Player.player_name == player['Player'])
                        player_data = {
                            player_name: player_name,
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
                            'player_id': player_instance.id_player,
                        }
                        PlayerStats.create(**player_data)