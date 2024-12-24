import requests
from bs4 import BeautifulSoup
from utils.team_name_abbrev import team_abbrev
from ratelimit import limits, sleep_and_retry

PERIOD = 60
CALLS = 5

class PlayerScraperAdvanced:
    
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/'
        # self.teams_NBA_list = ['ATL']
        self.teams_NBA_list = [teams for teams in team_abbrev.values()]
        self.years = ['2024']

    @sleep_and_retry 
    @limits(calls=CALLS, period=PERIOD)
    def fetch(self, url):
        print(f"Fetching URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        print(f"Finished fetching URL: {url}")
        return response.text

    def scrape_team_year_advanced(self, nba_team, year):
        print(f"Starting scrape for {nba_team} in {year}")
        url = f'https://www.basketball-reference.com/teams/{nba_team}/{year}.html'
        html_content = self.fetch(url)
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': 'advanced'})
        
        if table:
            print(f"Found advanced table for {nba_team} in {year}")
            headers = [th.text.strip() for th in table.find('thead').find_all('th')]
            rows = [
                {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(['th', 'td']))}
                for tr in table.find('tbody').find_all('tr')
            ]
            print(f"Scraping complete for {nba_team} in {year}")
            return rows
        else:
            print(f"No advanced table found for {nba_team} in {year}")
            return []

    def get_players_team_year_advanced(self):
        print("Starting to get players for all teams and years")
        dictionary_of_teams = {}

        for nba_team in self.teams_NBA_list:
            dictionary_of_teams[nba_team] = {}
            for year in self.years:
                print(f"Processing {nba_team} in {year}")
                advanced_stats = self.scrape_team_year_advanced(nba_team, year)
                dictionary_of_teams[nba_team][year] = advanced_stats

        # Reminder for skipping empty rows:
        # for team, years in dictionary_of_teams.items():
        #     for year, players in years.items():
        #         for player in players:
        #             dictionary_of_teams[team][year] = {k: v for k, v in player.items() if k != ''}

        print("Finished getting players for all teams and years")
        return dictionary_of_teams