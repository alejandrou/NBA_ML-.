from db_manager.db_conf import db
from scrap.scrap_team import TeamScraper
from scrap.scrap_player_roster import PlayerScraperRoster
from scrap.scrap_player_totals import PlayerScraperTotals
from models.team import Team
from models.player import Player
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
            teams_data = await self.scraper_player.get_players_team_year()

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