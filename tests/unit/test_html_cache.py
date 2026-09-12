import gzip
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from nba_data.scraping.cache import (
    METADATA_SCHEMA_VERSION,
    CacheFetchMetadata,
    CacheMetadataError,
    HtmlCache,
)

BOS_URL = "https://www.basketball-reference.com/teams/BOS/2024.html"
FETCHED_AT = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def _metadata(**overrides) -> CacheFetchMetadata:
    values = {
        "fetched_at": FETCHED_AT,
        "http_status": 200,
        "final_url": BOS_URL,
    }
    values.update(overrides)
    return CacheFetchMetadata(**values)


def _sidecar(**fields) -> str:
    """Render a sidecar body carrying a supported schema_version plus `fields`."""
    return json.dumps({"schema_version": METADATA_SCHEMA_VERSION, **fields})


@pytest.mark.unit
def test_html_cache_writes_and_reads_gzip(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = BOS_URL
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
    url = BOS_URL

    assert cache.path_for_url(url) == cache.path_for_url(url)
    assert "basketball-reference" in cache.path_for_url(url).parts


@pytest.mark.unit
def test_body_filename_for_a_known_url_did_not_change(tmp_path) -> None:
    """Four discovery regexes re-derive this shape rather than importing it."""
    cache = HtmlCache(tmp_path)

    assert cache.path_for_url(BOS_URL).name == "teams-bos-2024.html-8ef926a311c6bcbf.html.gz"


@pytest.mark.unit
def test_metadata_path_appends_the_sidecar_suffix_to_the_body_name(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    body_path = cache.path_for_url(BOS_URL)
    metadata_path = cache.metadata_path_for_url(BOS_URL)

    assert metadata_path.name == f"{body_path.name}.meta.json"
    assert metadata_path.parent == body_path.parent
    assert not metadata_path.name.endswith(".html.gz")


@pytest.mark.unit
def test_metadata_sidecar_is_outside_the_html_gz_glob(tmp_path) -> None:
    """Discovery globs `*.html.gz`; the sidecar must be invisible to it."""
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>ok</html>", metadata=_metadata())

    discovered = sorted(path.name for path in tmp_path.rglob("*.html.gz"))

    assert discovered == [cache.path_for_url(BOS_URL).name]


@pytest.mark.unit
def test_naive_fetched_at_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CacheFetchMetadata(
            fetched_at=datetime(2026, 3, 4, 5, 6, 7),
            http_status=200,
            final_url=BOS_URL,
        )


@pytest.mark.unit
def test_set_with_metadata_writes_the_sidecar_as_json(tmp_path) -> None:
    cache = HtmlCache(tmp_path)

    cache.set(BOS_URL, "<html>ok</html>", metadata=_metadata(http_status=200))

    payload = json.loads(cache.metadata_path_for_url(BOS_URL).read_text(encoding="utf-8"))

    assert payload == {
        "schema_version": METADATA_SCHEMA_VERSION,
        "fetched_at": "2026-03-04T05:06:07+00:00",
        "http_status": 200,
        "final_url": BOS_URL,
    }


@pytest.mark.unit
def test_set_with_metadata_leaves_no_temporary_files_behind(tmp_path) -> None:
    cache = HtmlCache(tmp_path)

    cache.set(BOS_URL, "<html>ok</html>", metadata=_metadata())

    written = sorted(path.name for path in tmp_path.rglob("*") if path.is_file())

    assert written == sorted(
        [
            cache.path_for_url(BOS_URL).name,
            cache.metadata_path_for_url(BOS_URL).name,
        ]
    )


@pytest.mark.unit
def test_get_metadata_round_trips_a_non_utc_offset(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    fetched_at = datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone(timedelta(hours=-5)))

    cache.set(BOS_URL, "<html>ok</html>", metadata=_metadata(fetched_at=fetched_at))
    recovered = cache.get_metadata(BOS_URL)

    assert recovered == _metadata(fetched_at=fetched_at)
    assert recovered is not None
    assert recovered.fetched_at.utcoffset() == timedelta(hours=-5)


@pytest.mark.unit
def test_get_metadata_recovers_the_recorded_provenance(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    redirected = "https://www.basketball-reference.com/teams/BOS/2024.html#all_roster"

    cache.set(BOS_URL, "<html>ok</html>", metadata=_metadata(final_url=redirected))

    assert cache.get_metadata(BOS_URL) == _metadata(final_url=redirected)


@pytest.mark.unit
def test_a_page_written_without_metadata_reports_unknown_provenance(tmp_path) -> None:
    """A bare `.html.gz` is how all 3,326 pre-existing pages look."""
    cache = HtmlCache(tmp_path)

    cache.set(BOS_URL, "<html>legacy</html>")

    assert cache.get(BOS_URL) == "<html>legacy</html>"
    assert cache.exists(BOS_URL) is True
    assert cache.get_metadata(BOS_URL) is None
    assert not cache.metadata_path_for_url(BOS_URL).exists()


@pytest.mark.unit
def test_set_without_metadata_removes_a_sidecar_from_a_previous_body(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>first</html>", metadata=_metadata())

    cache.set(BOS_URL, "<html>second</html>")

    assert cache.get(BOS_URL) == "<html>second</html>"
    assert cache.get_metadata(BOS_URL) is None
    assert not cache.metadata_path_for_url(BOS_URL).exists()


@pytest.mark.unit
def test_set_with_metadata_replaces_the_previous_sidecar(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>first</html>", metadata=_metadata(http_status=200))

    later = FETCHED_AT.replace(day=5)
    cache.set(BOS_URL, "<html>second</html>", metadata=_metadata(fetched_at=later))

    assert cache.get_metadata(BOS_URL) == _metadata(fetched_at=later)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("body", "expected_message"),
    [
        ("not json at all", "not valid JSON"),
        ("[]", "must be a JSON object"),
        (_sidecar(http_status=200, final_url="u"), "missing 'fetched_at'"),
        (_sidecar(fetched_at="2026-03-04T05:06:07+00:00", final_url="u"), "missing 'http_status'"),
        (_sidecar(fetched_at="2026-03-04T05:06:07+00:00", http_status=200), "missing 'final_url'"),
        (_sidecar(fetched_at=7, http_status=200, final_url="u"), "non-string 'fetched_at'"),
        (_sidecar(fetched_at="nope", http_status=200, final_url="u"), "unparseable 'fetched_at'"),
        (
            _sidecar(fetched_at="2026-03-04T05:06:07", http_status=200, final_url="u"),
            "naive 'fetched_at'",
        ),
        (
            _sidecar(fetched_at="2026-03-04T05:06:07+00:00", http_status="200", final_url="u"),
            "non-integer 'http_status'",
        ),
        (
            _sidecar(fetched_at="2026-03-04T05:06:07+00:00", http_status=200, final_url=7),
            "non-string 'final_url'",
        ),
    ],
)
def test_a_malformed_sidecar_is_an_error_not_unknown_provenance(
    tmp_path,
    body: str,
    expected_message: str,
) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>ok</html>")
    cache.metadata_path_for_url(BOS_URL).write_text(body, encoding="utf-8")

    with pytest.raises(CacheMetadataError, match=expected_message):
        cache.get_metadata(BOS_URL)


@pytest.mark.unit
@pytest.mark.parametrize("version", [2, 0, "1", None, 1.0, True, [1]])
def test_a_sidecar_with_an_unsupported_schema_version_is_an_error(tmp_path, version) -> None:
    """A shape this reader does not understand must not be read as version 1."""
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>ok</html>")
    payload = {
        "schema_version": version,
        "fetched_at": FETCHED_AT.isoformat(),
        "http_status": 200,
        "final_url": BOS_URL,
    }
    cache.metadata_path_for_url(BOS_URL).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CacheMetadataError, match="unsupported schema_version"):
        cache.get_metadata(BOS_URL)


@pytest.mark.unit
def test_a_sidecar_missing_its_schema_version_is_an_error(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>ok</html>")
    payload = {
        "fetched_at": FETCHED_AT.isoformat(),
        "http_status": 200,
        "final_url": BOS_URL,
    }
    cache.metadata_path_for_url(BOS_URL).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CacheMetadataError, match="unsupported schema_version"):
        cache.get_metadata(BOS_URL)


@pytest.mark.unit
def test_what_the_writer_writes_is_what_the_reader_accepts(tmp_path) -> None:
    """Guards the round trip: bumping one side without the other must fail here."""
    cache = HtmlCache(tmp_path)

    cache.set(BOS_URL, "<html>ok</html>", metadata=_metadata())

    assert cache.get_metadata(BOS_URL) == _metadata()


@pytest.mark.unit
def test_a_sidecar_that_is_not_utf8_is_an_error(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set(BOS_URL, "<html>ok</html>")
    cache.metadata_path_for_url(BOS_URL).write_bytes(b"\xff\xfe not utf-8")

    with pytest.raises(CacheMetadataError, match="not valid UTF-8"):
        cache.get_metadata(BOS_URL)


@pytest.mark.unit
@pytest.mark.parametrize("sidecar", ["absent", "present", "corrupt"])
def test_body_reads_are_unaffected_by_the_sidecar(tmp_path, sidecar: str) -> None:
    cache = HtmlCache(tmp_path)
    html = "<html>body</html>"
    cache.set(BOS_URL, html)
    if sidecar == "present":
        cache.set(BOS_URL, html, metadata=_metadata())
    elif sidecar == "corrupt":
        cache.metadata_path_for_url(BOS_URL).write_text("{", encoding="utf-8")

    assert cache.get(BOS_URL) == html
    assert cache.exists(BOS_URL) is True
