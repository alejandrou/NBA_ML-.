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



df = pd.DataFrame(rows, columns=headers)