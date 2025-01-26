from bs4 import BeautifulSoup
from utils.team_name_abbrev import team_abbrev
import asyncio
import httpx

class PlayerScraperRoster:
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/'
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        # self.teams_NBA_list = ['BOS']
        # self.years = range(2020, 2024)
        self.years = [2024]
        self.semaphore = asyncio.Semaphore(1)  # Limit to 20 requests per minute

    async def fetch(self, url, client):
        async with self.semaphore:
            # print(f"Fetching URL: {url}")
            try:
                response = await client.get(url)
                if response.status_code == 429:  # Rate limit exceeded
                    print("Rate limit exceeded. Sleeping for 60 seconds...")
                    await asyncio.sleep(60)
                    return await self.fetch(url, client)
                await asyncio.sleep(3)  # Space out requests
                # print(f"Finished fetching URL: {url}")
                return response.text
            except httpx.RequestError as exc:
                print(f"An error occurred: {exc}")
                return None

    async def scrape_team_year_roster(self, nba_team, year, client):
        # print(f"Scraping roster for {nba_team} in {year}")
        url = f'https://www.basketball-reference.com/teams/{nba_team}/{year}.html'
        html_content = await self.fetch(url, client)
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': 'roster'})

        if table:
            # print(f"Found roster table for {nba_team} in {year}")
            headers = [th.text.strip() for th in table.find('thead').find_all('th')]
            rows = [
                {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(['th', 'td']))}
                for tr in table.find('tbody').find_all('tr')
            ]
            # print(f"Scraping complete for {nba_team} in {year}")
            return rows
        else:
            print(f"No roster table found for {nba_team} in {year}")
            return []

    async def get_players_team_year_roster(self, client):
        results = {}
        tasks = []

        for nba_team in self.teams_NBA_list:
            results[nba_team] = {}
            for year in self.years:
                tasks.append(self.scrape_team_year_roster(nba_team, year, client))

        scraped_data = await asyncio.gather(*tasks)

        for i, (nba_team, year) in enumerate([(team, yr) for team in self.teams_NBA_list for yr in self.years]):
            results[nba_team][year] = scraped_data[i]

        return results