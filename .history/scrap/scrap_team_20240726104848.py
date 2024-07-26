import requests
from bs4 import BeautifulSoup
import pandas as pd

class TeamScraper:
    def __init__(self, url):
        self.url = url

    def get_team_table(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'teams_active'})
            if table:
                headers = [th.text.strip() for th in table.find('thead').find_all('th')]
                rows = [
                    [cell.text.strip() for cell in tr.find_all(['th', 'td'])]
                    for tr in table.find('tbody').find_all('tr', class_='full_table')
                ]

                df = pd.DataFrame(rows, columns=headers)
                return df
            else:
                raise ValueError("Could not find the table with id 'teams_active'")
        else:
            raise Exception(f"Failed to retrieve data, status code: {response.status_code}")