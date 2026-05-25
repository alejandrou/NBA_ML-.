import inspect
from pathlib import Path

import pytest

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.team_season_pages import (
    CachedBasketballReferencePageProvider,
    CachedTeamSeasonHtmlProvider,
    build_team_season_games_url,
    build_team_season_url,
    build_teams_index_url,
    fetch_basketball_reference_html,
    fetch_team_season_html,
    parse_cached_team_season_page,
)

FIXTURE = Path("tests/fixtures/html/team_season_minimal.html")
REALISTIC_FIXTURE = Path("tests/fixtures/html/team_season_realistic.html")


class FakeClient:
    def __init__(self, html: str = "<html>network</html>") -> None:
        self.html = html
        self.calls: list[tuple[str, bool]] = []

    def get(self, url: str, *, force_refresh: bool = False) -> str:
        self.calls.append((url, force_refresh))
        return self.html


@pytest.mark.unit
def test_build_team_season_url_is_deterministic() -> None:
    assert (
        build_team_season_url(" bos ", 2024)
        == "https://www.basketball-reference.com/teams/BOS/2024.html"
    )


@pytest.mark.unit
def test_build_team_season_url_rejects_empty_team() -> None:
    with pytest.raises(ValueError, match="team_abbreviation"):
        build_team_season_url(" ", 2024)


@pytest.mark.unit
def test_build_teams_index_url_is_deterministic() -> None:
    assert build_teams_index_url() == "https://www.basketball-reference.com/teams/"


@pytest.mark.unit
def test_build_team_season_games_url_is_deterministic() -> None:
    assert (
        build_team_season_games_url(" bos ", 2024)
        == "https://www.basketball-reference.com/teams/BOS/2024_games.html"
    )


@pytest.mark.unit
def test_fetch_basketball_reference_html_uses_cache_before_client(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_teams_index_url()
    html = "<html>teams index</html>"
    cache.set(url, html)
    client = FakeClient()

    assert fetch_basketball_reference_html(url, cache=cache, client=client) == html
    assert client.calls == []


@pytest.mark.unit
def test_fetch_basketball_reference_html_fetches_and_caches_on_miss(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_games_url("BOS", 2024)
    html = "<html>games</html>"
    client = FakeClient(html)

    assert fetch_basketball_reference_html(url, cache=cache, client=client) == html
    assert client.calls == [(url, False)]
    assert cache.get(url) == html
    assert cache.path_for_url(url).name.endswith(".html.gz")


@pytest.mark.unit
def test_fetch_basketball_reference_html_rejects_non_bref_url(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    client = FakeClient()

    with pytest.raises(ValueError, match="Basketball Reference URL"):
        fetch_basketball_reference_html("https://example.com/teams/", cache=cache, client=client)

    assert client.calls == []


@pytest.mark.unit
def test_fetch_team_season_html_uses_cache_before_client(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_url("BOS", 2024)
    html = FIXTURE.read_text(encoding="utf-8")
    cache.set(url, html)
    client = FakeClient()

    assert fetch_team_season_html("bos", 2024, cache=cache, client=client) == html
    assert client.calls == []


@pytest.mark.unit
def test_fetch_team_season_html_fetches_and_caches_on_miss(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    html = FIXTURE.read_text(encoding="utf-8")
    client = FakeClient(html)
    url = build_team_season_url("BOS", 2024)

    assert fetch_team_season_html("BOS", 2024, cache=cache, client=client) == html
    assert client.calls == [(url, False)]
    assert cache.get(url) == html


@pytest.mark.unit
def test_fetch_team_season_html_force_refresh_bypasses_cache(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_url("BOS", 2024)
    cache.set(url, "<html>cached</html>")
    client = FakeClient("<html>fresh</html>")

    assert fetch_team_season_html("BOS", 2024, cache=cache, client=client, force_refresh=True) == (
        "<html>fresh</html>"
    )
    assert client.calls == [(url, True)]
    assert cache.get(url) == "<html>fresh</html>"


@pytest.mark.unit
def test_cached_team_season_html_provider_uses_cache_before_client(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_url("BOS", 2024)
    html = REALISTIC_FIXTURE.read_text(encoding="utf-8")
    cache.set(url, html)
    client = FakeClient()
    provider = CachedTeamSeasonHtmlProvider(cache=cache, client=client)

    assert provider.get_html("bos", 2024) == html
    assert client.calls == []


@pytest.mark.unit
def test_cached_team_season_html_provider_fetches_once_and_stores_gzip(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    html = REALISTIC_FIXTURE.read_text(encoding="utf-8")
    client = FakeClient(html)
    provider = CachedTeamSeasonHtmlProvider(cache=cache, client=client)
    url = build_team_season_url("BOS", 2024)

    assert provider.get_html("BOS", 2024) == html
    assert provider.get_html("BOS", 2024) == html
    assert client.calls == [(url, False)]
    assert cache.get(url) == html
    assert cache.path_for_url(url).name.endswith(".html.gz")


@pytest.mark.unit
def test_cached_team_season_html_provider_can_use_generic_page_provider(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    html = REALISTIC_FIXTURE.read_text(encoding="utf-8")
    client = FakeClient(html)
    page_provider = CachedBasketballReferencePageProvider(cache=cache, client=client)
    provider = CachedTeamSeasonHtmlProvider(page_provider=page_provider)
    url = build_team_season_url("BOS", 2024)

    assert provider.get_html("BOS", 2024) == html
    assert provider.get_html("BOS", 2024) == html
    assert client.calls == [(url, False)]


@pytest.mark.unit
def test_parse_cached_team_season_page_routes_cached_html_to_parser(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_url("BOS", 2024)
    html = FIXTURE.read_text(encoding="utf-8")
    cache.set(url, html)

    parsed = parse_cached_team_season_page("bos", 2024, cache=cache)

    assert parsed["roster"] == [{"No.": "0", "Player": "Jayson Tatum", "Pos": "SF"}]
    assert parsed["totals"] == [{"player": "Jayson Tatum", "g": "74", "pts": "1987"}]
    assert parsed["advanced"] == [{"player": "Jayson Tatum", "per": "22.3"}]


@pytest.mark.unit
def test_parse_cached_team_season_page_reads_realistic_fixture(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_url("BOS", 2024)
    html = REALISTIC_FIXTURE.read_text(encoding="utf-8")
    cache.set(url, html)

    parsed = parse_cached_team_season_page("BOS", 2024, cache=cache)

    assert [row["player"] for row in parsed["roster"]] == [
        "Jayson Tatum",
        "Jaylen Brown",
    ]
    assert [row["pts"] for row in parsed["totals"]] == ["1987", "1644"]
    assert [row["per"] for row in parsed["advanced"]] == ["22.3", "19.1"]


@pytest.mark.unit
def test_parse_cached_team_season_page_raises_on_cache_miss(tmp_path) -> None:
    cache = HtmlCache(tmp_path)

    with pytest.raises(FileNotFoundError, match="Cached team-season HTML not found"):
        parse_cached_team_season_page("BOS", 2024, cache=cache)


@pytest.mark.unit
def test_parse_cached_team_season_page_does_not_accept_client() -> None:
    signature = inspect.signature(parse_cached_team_season_page)

    assert "client" not in signature.parameters
