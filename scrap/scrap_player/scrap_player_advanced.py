import aiohttp
import asyncio
from bs4 import BeautifulSoup

class PlayerScraperAdvanced:
    
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/'
        self.teams_NBA_list = ['ATL']
        self.years = ['2024']

    async def fetch(self, session, url):
        print(f"Fetching URL: {url}")
        async with session.get(url) as response:
            content = await response.text()
            print(f"Finished fetching URL: {url}")
            return content

    async def scrape_team_year_advanced(self, session, nba_team, year):
        print(f"Starting scrape for {nba_team} in {year}")
        url = f'https://www.basketball-reference.com/teams/{nba_team}/{year}.html'
        html_content = await self.fetch(session, url)
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': 'advanced'})
        
        if table:
            print(f"Found roster table for {nba_team} in {year}")
            headers = [th.text.strip() for th in table.find('thead').find_all('th')]
            rows = [
                {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(['th', 'td']))}
                for tr in table.find('tbody').find_all('tr')
            ]
            print(f"Scraping complete for {nba_team} in {year}")
            return rows
        else:
            print(f"No roster table found for {nba_team} in {year}")
            return []

    async def get_players_team_year_advanced(self):
        print("Starting to get players for all teams and years")
        dictionary_of_teams = {}
        async with aiohttp.ClientSession() as session:
            tasks = []
            for nba_team in self.teams_NBA_list:
                dictionary_of_teams[nba_team] = {}
                for year in self.years:
                    print(f"Queueing task for {nba_team} in {year}")
                    task = asyncio.create_task(self.scrape_team_year_advanced(session, nba_team, year))
                    dictionary_of_teams[nba_team][year] = task
                    tasks.append(task)

            print("All tasks queued, waiting for completion...")
            results = await asyncio.gather(*tasks)
            print("All tasks completed.")

            for i, nba_team in enumerate(self.teams_NBA_list):
                for j, year in enumerate(self.years):
                    dictionary_of_teams[nba_team][year] = results[i * len(self.years) + j]

            # I put it as a reminder that in the dboperations if a player doesnt exist "skips it" so basically if there is an empty row it will skip it to the next player
            # So this doesnt need any cleanse
            # for team, years in dictionary_of_teams.items():
            #     for year, players in years.items():
            #         for player in players:
            #             dictionary_of_teams[team][year] = {k : v for k, v in player.items() if k != ''}
            
        print("Finished getting players for all teams and years")
        return dictionary_of_teams