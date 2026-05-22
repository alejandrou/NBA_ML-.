from pathlib import Path

import pytest
from db_manager.team_operations.team_operations import TeamOperations
from scrap.scrap_team.scrap_team import TeamScraper
from scrap.scrap_team.scrap_team_regular_season_results import TeamScraperRegularSeasonResults

from nba_data.scraping.team_season_pages import build_team_season_games_url, build_teams_index_url

TEAMS_FIXTURE = Path("tests/fixtures/html/teams_index_minimal.html")
GAMES_FIXTURE = Path("tests/fixtures/html/team_games_minimal.html")


class FakePageProvider:
    def __init__(self, html_by_url: dict[str, str]) -> None:
        self.html_by_url = html_by_url
        self.calls: list[str] = []

    def get_html(self, url: str) -> str:
        self.calls.append(url)
        return self.html_by_url[url]


@pytest.mark.unit
def test_team_scraper_reads_teams_index_through_provider() -> None:
    url = build_teams_index_url()
    provider = FakePageProvider({url: TEAMS_FIXTURE.read_text(encoding="utf-8")})
    scraper = TeamScraper(provider)

    rows = scraper.get_team_table()

    assert provider.calls == [url]
    assert rows == [
        {
            "Team": "Boston Celtics",
            "Lg": "NBA",
            "From": "1947",
            "To": "2024",
            "W": "3600",
            "L": "2500",
            "W/L%": ".590",
            "Plyfs": "60",
            "Div": "34",
            "Conf": "11",
            "Champ": "18",
        }
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_team_regular_season_results_reads_games_through_provider() -> None:
    url = build_team_season_games_url("BOS", 2024)
    provider = FakePageProvider({url: GAMES_FIXTURE.read_text(encoding="utf-8")})
    scraper = TeamScraperRegularSeasonResults([2024], provider)

    rows = await scraper.scrape_team_year_results("BOS", 2024)

    assert provider.calls == [url]
    assert rows == [
        {
            "g": "1",
            "date_game": "2023-10-25",
            "opp_name": "New York Knicks",
            "game_result": "W",
            "pts": "108",
            "opp_pts": "104",
            "wins": "1",
            "losses": "0",
        }
    ]


@pytest.mark.unit
def test_team_operations_wires_provider_into_team_scrapers() -> None:
    provider = FakePageProvider({})

    operations = TeamOperations([2024], page_provider=provider)

    assert operations.scraper_team.page_provider is provider
    assert operations.scraper_team_regular_season.page_provider is provider


@pytest.mark.unit
def test_consolidated_team_scrapers_do_not_keep_direct_live_http_paths() -> None:
    paths = [
        Path("scrap/scrap_team/scrap_team.py"),
        Path("scrap/scrap_team/scrap_team_regular_season_results.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "requests.get" not in source
    assert "httpx" not in source
    assert "AsyncClient" not in source
    assert "client.get" not in source
    assert "asyncio.sleep" not in source
    assert "asyncio.gather" not in source
