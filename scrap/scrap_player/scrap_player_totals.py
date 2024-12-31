from bs4 import BeautifulSoup, Comment
from utils.team_name_abbrev import team_abbrev
import asyncio
import httpx

class PlayerScraperTotals:
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/'
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        self.years = ['2024']
        self.semaphore = asyncio.Semaphore(1)  # 20 requests per minute

    async def fetch(self, url, client):
        async with self.semaphore:
            print(f"Fetching URL: {url}")
            try:
                response = await client.get(url)
                if response.status_code == 429:  # Handle rate limiting
                    print("Rate limit exceeded. Sleeping for 60 seconds...")
                    await asyncio.sleep(60)
                    return await self.fetch(url, client)
                await asyncio.sleep(3)  # Introduce delay
                print(f"Finished fetching URL: {url}")
                return response.text
            except httpx.RequestError as exc:
                print(f"An error occurred: {exc}")
                return None

    async def scrape_team_year_totals(self, nba_team, year, client):
        url = f"https://www.basketball-reference.com/teams/{nba_team}/{year}.html"
        html_content = await self.fetch(url, client)

        if not html_content:
            print(f"No content found for {nba_team} in {year}.")
            return []

        soup = BeautifulSoup(html_content, "html.parser")

        # Locate the commented section
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))

        for comment in comments:
            if "totals_stats" in comment:  # Check if the desired table is inside the comment
                comment_soup = BeautifulSoup(comment, "html.parser")  # Parse the commented content
                table = comment_soup.find("table", {"id": "totals_stats"})
                if table:
                    print(f"Found totals table for {nba_team} in {year}")
                    headers = [th.text.strip() for th in table.find("thead").find_all("th")]
                    rows = [
                        {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(["th", "td"]))}
                        for tr in table.find("tbody").find_all("tr")
                    ]
                    return rows

        print(f"Totals table not found for {nba_team} in {year}.")
        return []

    async def get_players_team_year_totals(self, client):
        results = {}
        tasks = []

        for nba_team in self.teams_NBA_list:
            results[nba_team] = {}
            for year in self.years:
                tasks.append(self.scrape_team_year_totals(nba_team, year, client))

        scraped_data = await asyncio.gather(*tasks)

        for i, (nba_team, year) in enumerate([(team, yr) for team in self.teams_NBA_list for yr in self.years]):
            results[nba_team][year] = scraped_data[i]

        return results