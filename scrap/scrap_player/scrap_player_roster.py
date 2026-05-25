from scrap.scrap_player.team_season_adapter import LegacyTeamSeasonTableAdapter
from utils.team_name_abbrev import team_abbrev


class PlayerScraperRoster:
    def __init__(self, years, team_season_html_provider=None, team_season_table_adapter=None):
        self.url = "https://www.basketball-reference.com/teams/"
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        self.years = years
        self.team_season_table_adapter = team_season_table_adapter or LegacyTeamSeasonTableAdapter(
            team_season_html_provider
        )
        self.team_season_html_provider = self.team_season_table_adapter.team_season_html_provider

    async def scrape_team_year_roster(self, nba_team, year, client=None):
        print(f"Scraping roster for {nba_team} in {year}")
        rows = self.team_season_table_adapter.get_roster(nba_team, year)
        print(f"Scraping complete for {nba_team} in {year}")
        return rows

    async def get_players_team_year_roster(self, client=None):
        results = {}

        for nba_team in self.teams_NBA_list:
            results[nba_team] = {}
            for year in self.years:
                results[nba_team][year] = await self.scrape_team_year_roster(nba_team, year)

        return results
