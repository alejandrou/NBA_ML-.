from bs4 import BeautifulSoup

from nba_data.scraping.team_season_pages import build_teams_index_url


class TeamScraper:
    def __init__(self, page_provider=None):
        self.url = build_teams_index_url()
        self.page_provider = page_provider

    def get_team_table(self):
        if self.page_provider is None:
            raise ValueError("page_provider is required")

        html = self.page_provider.get_html(self.url)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": "teams_active"})

        if not table:
            raise ValueError("Could not find the table with id 'teams_active'")

        headers = [th.text.strip() for th in table.find("thead").find_all("th")]
        headers = ["Team" if header == "Franchise" else header for header in headers]

        return [
            {headers[i]: cell.text.strip() for i, cell in enumerate(tr.find_all(["th", "td"]))}
            for tr in table.find("tbody").find_all("tr", class_="full_table")
        ]
