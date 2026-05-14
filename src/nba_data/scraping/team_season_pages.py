from __future__ import annotations

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import BasketballReferenceClient

BASE_URL = "https://www.basketball-reference.com"


def build_team_season_url(team_abbreviation: str, year: int) -> str:
    team = team_abbreviation.strip().upper()
    if not team:
        msg = "team_abbreviation must not be empty"
        raise ValueError(msg)
    return f"{BASE_URL}/teams/{team}/{year}.html"


def fetch_team_season_html(
    team_abbreviation: str,
    year: int,
    *,
    cache: HtmlCache,
    client: BasketballReferenceClient,
    force_refresh: bool = False,
) -> str:
    url = build_team_season_url(team_abbreviation, year)

    if not force_refresh:
        cached = cache.get(url)
        if cached is not None:
            return cached

    html = client.get(url, force_refresh=force_refresh)
    cache.set(url, html)
    return html
