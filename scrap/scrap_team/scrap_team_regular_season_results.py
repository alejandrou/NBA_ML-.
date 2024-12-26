import time
from bs4 import BeautifulSoup
from utils.team_name_abbrev import team_abbrev
import httpx
import asyncio


class TeamScraperRegularSeasonResults:
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/'
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        self.years = ['2024']
        self.semaphore = asyncio.Semaphore(20)  # Allow up to 20 concurrent requests per minute

    async def fetch(self, url, client):
        async with self.semaphore:  # Limit concurrent requests
            print(f"Fetching URL: {url}")
            try:
                response = await client.get(url)
                if response.status_code == 429:  # Too Many Requests
                    print("Rate limit exceeded. Sleeping for 60 seconds...")
                    await asyncio.sleep(60)  # Backoff strategy
                    return await self.fetch(url, client)
                await asyncio.sleep(3)  # Space out requests by 3 seconds
                print(f"Finished fetching URL: {url}")
                return response.text
            except httpx.RequestError as exc:
                print(f"An error occurred while requesting {url}: {exc}")
                return None

    async def scrape_team_year_results(self, nba_team, year, client):
        print(f"Starting scrape for {nba_team} in {year}")
        url = f'https://www.basketball-reference.com/teams/{nba_team}/{year}_games.html'
        html_content = await self.fetch(url, client)
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': 'games'})

        if table:
            print(f"Found game results table for {nba_team} in {year}")
            headers = [th['data-stat'] for th in table.find('thead').find_all('th')]
            rows = []
            for tr in table.find('tbody').find_all('tr'):
                if 'thead' in tr.get('class', []) or (tr.find('th') and tr.find('th').text.strip() == headers[0]):
                    continue
                row_data = {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(['th', 'td']))}
                rows.append(row_data)
            print(f"Scraping complete for {nba_team} in {year}")
            return rows
        else:
            print(f"No game results table found for {nba_team} in {year}")
            return []

    async def get_team_regular_season_results_async(self, client):
        results = {}
        tasks = []

        # Prepare async tasks for each team and year
        for nba_team in self.teams_NBA_list:
            results[nba_team] = {}
            for year in self.years:
                tasks.append(self.scrape_team_year_results(nba_team, year, client))

        # Gather results
        scraped_data = await asyncio.gather(*tasks)

        # Organize results by team and year
        for i, (nba_team, year) in enumerate([(team, yr) for team in self.teams_NBA_list for yr in self.years]):
            results[nba_team][year] = scraped_data[i]

        return results
