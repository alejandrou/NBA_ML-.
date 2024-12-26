from scrap.scrap_team.scrap_team import TeamScraper
from scrap.scrap_team.scrap_team_regular_season_results import TeamScraperRegularSeasonResults
from models.team.team import Team
from models.team.team_regular_season_results import TeamRegularSeasonResults
from utils.team_name_abbrev import team_abbrev
from db_manager.db_manager import DBManager

class TeamOperations:
    
    def __init__(self):
        self.scraper_team = TeamScraper()
        self.scraper_team_regular_season = TeamScraperRegularSeasonResults()

    def scrape_and_save_teams(self):
        team_data = self.scraper_team.get_team_table()
        DBManager.create_tables(Team)

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

    async def scrape_and_save_teams_season_results_async(self, client):
        DBManager.create_tables(TeamRegularSeasonResults)

        # Scrape data with respect to rate limits
        team_regular_season_results = await self.scraper_team_regular_season.get_team_regular_season_results_async(client)

        for team_name, years_data in team_regular_season_results.items():
            team_instance = Team.get(Team.team_abbreviation == team_name)

            batch_data = []  # Collect data for batch insertion
            for year, teams in years_data.items():
                for team in teams:
                    team_data = {
                        'id_team': team_instance.id_team,
                        'game': team.get('g', None),
                        'date_game': team.get('date_game', None),
                        'game_start_time': team.get('game_start_time', None),
                        'network': team.get('network', None),
                        'box_score_text': team.get('box_score_text', None),
                        'game_location': team.get('game_location', None),
                        'opp_name': team.get('opp_name', None),
                        'game_result': team.get('game_result', None),
                        'overtimes': team.get('overtimes', None),
                        'pts': team.get('pts', None),
                        'opp_pts': team.get('opp_pts', None),
                        'wins': team.get('wins', None),
                        'losses': team.get('losses', None),
                        'game_streak': team.get('game_streak', None),
                        'attendance': team.get('attendance', None),
                        'game_duration': team.get('game_duration', None),
                        'game_remarks': team.get('game_remarks', None),
                        'year': year
                    }
                    batch_data.append(team_data)

            # Batch insert
            if batch_data:
                TeamRegularSeasonResults.insert_many(batch_data).execute()