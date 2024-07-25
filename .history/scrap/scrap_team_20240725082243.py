import requests
from bs4 import BeautifulSoup
import pandas as pd


url = 'https://www.basketball-reference.com/teams/'
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')
table = soup.find('table', {'id': 'teams_active'})
headers = [th.text.strip() for th in table.find('thead').find_all('th')]
rows = [
    [cell.text.strip() for cell in tr.find_all(['th', 'td'])]
    for tr in table.find('tbody').find_all('tr', class_='full_table')
]

df = pd.DataFrame(rows, columns=headers)