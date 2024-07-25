import requests
from bs4 import BeautifulSoup
import pandas as pd

def fetch_html(url):
    response = requests.get(url)
    return response.content

def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    return soup

def extract_table(soup, table_id):
    return soup.find('table', {'id': table_id})

def extract_data(table):
    headers = [th.text.strip() for th in table.find('thead').find_all('th')]
    rows = [
        [cell.text.strip() for cell in tr.find_all(['th', 'td'])]
        for tr in table.find('tbody').find_all('tr', class_='full_table')
    ]
    return pd.DataFrame(rows, columns=headers)