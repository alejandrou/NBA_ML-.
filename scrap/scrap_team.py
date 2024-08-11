import requests
from bs4 import BeautifulSoup
import pandas as pd

class TeamScraper:
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/'

    def get_team_table(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'teams_active'})
            if table:
                headers = [th.text.strip() for th in table.find('thead').find_all('th')]
                headers = ['Team' if header == 'Franchise' else header for header in headers]
                
                rows = [
                    {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(['th', 'td']))}
                    for tr in table.find('tbody').find_all('tr', class_='full_table')
                ]
                
                return rows
            else:
                raise ValueError("Could not find the table with id 'teams_active'")
        else:
            raise Exception(f"Failed to retrieve data, status code: {response.status_code}")