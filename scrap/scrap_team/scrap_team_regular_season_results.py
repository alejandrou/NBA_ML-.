import requests
from bs4 import BeautifulSoup


class TeamScraperRegularSeasonResults:
    def __init__(self):
        self.url = 'https://www.basketball-reference.com/teams/',
        self.teams_NBA_list = 'ATL',
        self.years = '2024',

    async def get_team_regular_season_results(self):
        dictionary_of_teams = {}
        for nba_team in self.teams_NBA_list:
            dictionary_of_teams[nba_team] = {}
            for year in self.years:
                dictionary_of_teams[nba_team][year] = []
                url = f'https://www.basketball-reference.com/teams/{nba_team}/{year}_games.html'
                response = requests.get(url)
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'id': 'games'})
                if table:
                    headers = [th['data-stat'] for th in table.find('thead').find_all('th')]
                    for tr in table.find('tbody').find_all('tr'):
                        # Ignorar los tr que tienen la clase 'thead'
                        if 'thead' in tr.get('class', []):
                            continue
                        # Ignorar filas que tienen un th con el valor del primer header
                        if tr.find('th') and tr.find('th').text.strip() == headers[0]:
                            continue
                        row_data = {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(['th', 'td']))}
                        dictionary_of_teams[nba_team][year].append(row_data)
        return dictionary_of_teams
