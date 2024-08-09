import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

class PlayerScraper:
    
    def __init__(self):
        self.url = f'https://www.basketball-reference.com/teams/'
        self.teams_NBA_list = ['ATL', 'BOS']
        self.years = ['2024', '2023']

    def get_players_team_year(self):
        dictionary_of_teams = {}
        for nba_team in self.teams_NBA_list:
            dictionary_of_teams[nba_team] = {}
            for year in self.years:
                dictionary_of_teams[nba_team][year] = {}
                self.url = f'https://www.basketball-reference.com/teams/{nba_team}/{year}.html'
                response = requests.get(self.url)
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'id': 'roster'})
                if table:
                    headers = [th.text.strip() for th in table.find('thead').find_all('th')]
                    rows = [
                            [cell.text.strip() for cell in tr.find_all(['th', 'td'])]
                            for tr in table.find('tbody').find_all('tr')
                        ]
                    df = pd.DataFrame(rows, columns=headers)
                    df.reset_index(drop=True, inplace=True)
                    dictionary_of_teams[nba_team][year] = df
                    time.sleep(3)
        return dictionary_of_teams