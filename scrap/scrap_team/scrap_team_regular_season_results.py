from bs4 import BeautifulSoup

from nba_data.scraping.team_season_pages import build_team_season_games_url
from utils.team_name_abbrev import team_abbrev


class TeamScraperRegularSeasonResults:
    def __init__(self, years, page_provider=None):
        self.url = "https://www.basketball-reference.com/teams/"
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        self.years = years
        self.page_provider = page_provider

    async def scrape_team_year_results(self, nba_team, year, client=None):
        if self.page_provider is None:
            raise ValueError("page_provider is required")

        print(f"Starting scrape for {nba_team} in {year}")
        url = build_team_season_games_url(nba_team, year)
        html_content = self.page_provider.get_html(url)
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find("table", {"id": "games"})

        if table:
            print(f"Found game results table for {nba_team} in {year}")
            headers = [th["data-stat"] for th in table.find("thead").find_all("th")]
            rows = []
            for tr in table.find("tbody").find_all("tr"):
                if "thead" in tr.get("class", []) or (
                    tr.find("th") and tr.find("th").text.strip() == headers[0]
                ):
                    continue
                row_data = {
                    headers[i]: cell.text.strip()
                    for i, cell in enumerate(tr.find_all(["th", "td"]))
                }
                rows.append(row_data)
            print(f"Scraping complete for {nba_team} in {year}")
            return rows

        print(f"No game results table found for {nba_team} in {year}")
        return []

    async def get_team_regular_season_results_async(self, client=None):
        results = {}

        for nba_team in self.teams_NBA_list:
            results[nba_team] = {}
            for year in self.years:
                results[nba_team][year] = await self.scrape_team_year_results(nba_team, year)

        return results
