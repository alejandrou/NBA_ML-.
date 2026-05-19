from __future__ import annotations

from typing import Protocol

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import BasketballReferenceClient
from nba_data.scraping.parsers.team_season import parse_team_season_page

BASE_URL = "https://www.basketball-reference.com"


class TeamSeasonHtmlProvider(Protocol):
    def get_html(self, team_abbreviation: str, year: int) -> str:
        """Return raw HTML for one team-season page."""


class CachedTeamSeasonHtmlProvider:
    def __init__(
        self,
        *,
        cache: HtmlCache,
        client: BasketballReferenceClient,
        force_refresh: bool = False,
    ) -> None:
        self.cache = cache
        self.client = client
        self.force_refresh = force_refresh

    def get_html(self, team_abbreviation: str, year: int) -> str:
        return fetch_team_season_html(
            team_abbreviation,
            year,
            cache=self.cache,
            client=self.client,
            force_refresh=self.force_refresh,
        )


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


def parse_cached_team_season_page(
    team_abbreviation: str,
    year: int,
    *,
    cache: HtmlCache,
) -> dict[str, list[dict[str, str]]]:
    url = build_team_season_url(team_abbreviation, year)
    html = cache.get(url)
    if html is None:
        msg = f"Cached team-season HTML not found for {url}"
        raise FileNotFoundError(msg)
    return parse_team_season_page(html)
