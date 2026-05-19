from bs4 import BeautifulSoup, Comment
from utils.team_name_abbrev import team_abbrev
import asyncio
import httpx


class PlayerScraperAdvanced:

    def __init__(self, years, team_season_html_provider=None):
        self.url = 'https://www.basketball-reference.com/teams/'
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        self.years = years
        self.semaphore = asyncio.Semaphore(1) 
        self.team_season_html_provider = team_season_html_provider

    async def fetch(self, url, client):
        async with self.semaphore:
            print(f"Fetching URL: {url}")
            try:
                response = await client.get(url)
                if response.status_code == 429: 
                    print("Rate limit exceeded. Sleeping for 60 seconds...")
                    await asyncio.sleep(60)
                    return await self.fetch(url, client)
                await asyncio.sleep(3)  # Introduce delay
                print(f"Finished fetching URL: {url}")
                return response.text
            except httpx.RequestError as exc:
                print(f"An error occurred: {exc}")
                return None

    async def get_team_season_html(self, nba_team, year, client=None):
        if self.team_season_html_provider is not None:
            return self.team_season_html_provider.get_html(nba_team, year)
        if client is None:
            raise ValueError("client is required when team_season_html_provider is not configured")
        url = f"https://www.basketball-reference.com/teams/{nba_team}/{year}.html"
        return await self.fetch(url, client)

    async def scrape_team_year_advanced(self, nba_team, year, client=None):
        html_content = await self.get_team_season_html(nba_team, year, client)

        if not html_content:
            print(f"No content found for {nba_team} in {year}.")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))

        for comment in comments:
            if "advanced" in comment:  
                comment_soup = BeautifulSoup(comment, "html.parser") 
                table = comment_soup.find("table", {"id": "advanced"})
                if table:
                    print(f"Found advanced table for {nba_team} in {year}")
                    headers = [th.text.strip() for th in table.find("thead").find_all("th")]
                    rows = [
                        {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(["th", "td"]))}
                        for tr in table.find("tbody").find_all("tr")
                    ]
                    return rows

        print(f"Totals table not found for {nba_team} in {year}.")
        return []

    async def get_players_team_year_advanced(self, client=None):
        results = {}
        tasks = []

        for nba_team in self.teams_NBA_list:
            results[nba_team] = {}
            for year in self.years:
                tasks.append(self.scrape_team_year_advanced(nba_team, year, client))

        scraped_data = await asyncio.gather(*tasks)

        for i, (nba_team, year) in enumerate([(team, yr) for team in self.teams_NBA_list for yr in self.years]):
            results[nba_team][year] = scraped_data[i]

        return results
