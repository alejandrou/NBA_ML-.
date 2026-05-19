import gzip

import pytest

from nba_data.scraping.cache import HtmlCache


@pytest.mark.unit
def test_html_cache_writes_and_reads_gzip(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = "https://www.basketball-reference.com/teams/BOS/2024.html"
    html = "<html><body>hello</body></html>"

    path = cache.set(url, html)

    assert path.suffix == ".gz"
    assert path.name.endswith(".html.gz")
    assert path.exists()
    assert cache.exists(url)
    assert cache.get(url) == html
    with gzip.open(path, "rt", encoding="utf-8") as file:
        assert file.read() == html


@pytest.mark.unit
def test_html_cache_returns_none_for_missing_url(tmp_path) -> None:
    cache = HtmlCache(tmp_path)

    assert cache.get("https://www.basketball-reference.com/teams/BOS/2025.html") is None


@pytest.mark.unit
def test_html_cache_key_is_stable(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = "https://www.basketball-reference.com/teams/BOS/2024.html"

    assert cache.path_for_url(url) == cache.path_for_url(url)
    assert "basketball-reference" in cache.path_for_url(url).parts
