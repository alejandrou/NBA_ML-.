from pathlib import Path

import pytest

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.team_season_pages import build_team_season_url, fetch_team_season_html

FIXTURE = Path("tests/fixtures/html/team_season_minimal.html")


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
