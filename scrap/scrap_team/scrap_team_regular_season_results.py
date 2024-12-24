import requests
import time
from bs4 import BeautifulSoup
from utils.team_name_abbrev import team_abbrev

class TeamScraperRegularSeasonResults:
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/'
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        self.years = ['2024']

    def fetch(self, url):
        print(f"Fetching URL: {url}")
        response = requests.get(url)
        time.sleep(5)  # Simular el comportamiento de un usuario, esperando 3 segundos entre solicitudes
        print(f"Finished fetching URL: {url}")
        return response.text

    def scrape_team_year_results(self, nba_team, year):
        print(f"Starting scrape for {nba_team} in {year}")
        url = f'https://www.basketball-reference.com/teams/{nba_team}/{year}_games.html'
        html_content = self.fetch(url)
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

    def get_team_regular_season_results(self):
        print("Starting to get game results for all teams and years")
        dictionary_of_teams = {}
        for nba_team in self.teams_NBA_list:
            dictionary_of_teams[nba_team] = {}
            for year in self.years:
                print(f"Scraping {nba_team} for {year}")
                result = self.scrape_team_year_results(nba_team, year)
                dictionary_of_teams[nba_team][year] = result

        print("Finished getting game results for all teams and years")
        return dictionary_of_teams
