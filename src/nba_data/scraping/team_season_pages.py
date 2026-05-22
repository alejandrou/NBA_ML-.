from __future__ import annotations

from typing import Protocol
from urllib.parse import urlparse

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import BasketballReferenceClient
from nba_data.scraping.parsers.team_season import parse_team_season_page

BASE_URL = "https://www.basketball-reference.com"


class BasketballReferencePageProvider(Protocol):
    def get_html(self, url: str) -> str:
        """Return raw HTML for one Basketball Reference URL."""


class TeamSeasonHtmlProvider(Protocol):
    def get_html(self, team_abbreviation: str, year: int) -> str:
        """Return raw HTML for one team-season page."""


class CachedBasketballReferencePageProvider:
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

    def get_html(self, url: str) -> str:
        return fetch_basketball_reference_html(
            url,
            cache=self.cache,
            client=self.client,
            force_refresh=self.force_refresh,
        )


class CachedTeamSeasonHtmlProvider:
    def __init__(
        self,
        *,
        cache: HtmlCache | None = None,
        client: BasketballReferenceClient | None = None,
        force_refresh: bool = False,
        page_provider: BasketballReferencePageProvider | None = None,
    ) -> None:
        if page_provider is None:
            if cache is None or client is None:
                msg = "cache and client are required when page_provider is not supplied"
                raise ValueError(msg)
            page_provider = CachedBasketballReferencePageProvider(
                cache=cache,
                client=client,
                force_refresh=force_refresh,
            )
        self.page_provider = page_provider

    def get_html(self, team_abbreviation: str, year: int) -> str:
        return self.page_provider.get_html(build_team_season_url(team_abbreviation, year))


def build_teams_index_url() -> str:
    return f"{BASE_URL}/teams/"


def build_team_season_url(team_abbreviation: str, year: int) -> str:
    team = team_abbreviation.strip().upper()
    if not team:
        msg = "team_abbreviation must not be empty"
        raise ValueError(msg)
    return f"{BASE_URL}/teams/{team}/{year}.html"


def build_team_season_games_url(team_abbreviation: str, year: int) -> str:
    team = team_abbreviation.strip().upper()
    if not team:
        msg = "team_abbreviation must not be empty"
        raise ValueError(msg)
    return f"{BASE_URL}/teams/{team}/{year}_games.html"


def fetch_basketball_reference_html(
    url: str,
    *,
    cache: HtmlCache,
    client: BasketballReferenceClient,
    force_refresh: bool = False,
) -> str:
    _validate_basketball_reference_url(url)

    if not force_refresh:
        cached = cache.get(url)
        if cached is not None:
            return cached

    html = client.get(url, force_refresh=force_refresh)
    cache.set(url, html)
    return html


def fetch_team_season_html(
    team_abbreviation: str,
    year: int,
    *,
    cache: HtmlCache,
    client: BasketballReferenceClient,
    force_refresh: bool = False,
) -> str:
    url = build_team_season_url(team_abbreviation, year)
    return fetch_basketball_reference_html(
        url,
        cache=cache,
        client=client,
        force_refresh=force_refresh,
    )


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


def _validate_basketball_reference_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if parsed.scheme not in {"http", "https"} or host != "basketball-reference.com":
        msg = f"Expected a Basketball Reference URL, got {url!r}"
        raise ValueError(msg)
