import gzip
import inspect
from pathlib import Path

import pytest

import nba_data.scraping.offline_processor as offline_processor
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonSource,
    process_offline_team_season_sources,
)
from nba_data.scraping.team_season_pages import build_team_season_games_url, build_team_season_url

PHASE3_FIXTURE = Path("tests/fixtures/html/team_season_phase3.html")
MINIMAL_FIXTURE = Path("tests/fixtures/html/team_season_minimal.html")


class NoWriteHtmlCache(HtmlCache):
    def set(self, url: str, html: str) -> Path:
        raise AssertionError("offline processor must not refresh cache misses")


@pytest.mark.unit
def test_process_offline_team_season_url_reads_cached_gzip_and_validates_rows(
    tmp_path,
) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_url("BOS", 2024)
    cache_path = cache.path_for_url(url)
    _write_gzip(cache_path, PHASE3_FIXTURE.read_text(encoding="utf-8"))

    report = process_offline_team_season_sources(
        [OfflineTeamSeasonSource.from_url(url)],
        cache=cache,
        required_tables={"roster", "totals", "advanced"},
    )

    assert report.total_inputs == 1
    assert report.validated_entries == 1
    assert report.failed_entries == 0
    assert report.validated_row_count == 9
    assert report.validated_rows == report.entries[0].normalized_rows

    entry = report.entries[0]
    assert entry.status == "validated"
    assert entry.source.source_type == "url"
    assert entry.source.url == url
    assert entry.source.cache_path == str(cache_path)
    assert {row["source_table"] for row in entry.normalized_rows} >= {
        "roster",
        "totals",
        "advanced",
    }
    assert all(row["team_abbreviation"] == "BOS" for row in entry.normalized_rows)


@pytest.mark.unit
def test_process_offline_team_season_explicit_path_under_cache_root(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    cache_path = cache.root_dir / "basketball-reference" / "fixture.html.gz"
    _write_gzip(cache_path, PHASE3_FIXTURE.read_text(encoding="utf-8"))

    report = process_offline_team_season_sources(
        [
            OfflineTeamSeasonSource.from_path(
                cache_path,
                team_abbreviation="bos",
                season_year=2024,
            )
        ],
        cache=cache,
    )

    assert report.validated_entries == 1
    assert report.failed_entries == 0
    assert report.entries[0].source.source_type == "path"
    assert report.entries[0].source.url is None
    assert report.entries[0].source.team_abbreviation == "BOS"


@pytest.mark.unit
def test_cache_miss_reports_failure_and_does_not_block_other_inputs(tmp_path) -> None:
    cache = NoWriteHtmlCache(tmp_path)
    missing_url = build_team_season_url("BOS", 2024)
    cached_url = build_team_season_url("DEN", 2023)
    _write_gzip(cache.path_for_url(cached_url), PHASE3_FIXTURE.read_text(encoding="utf-8"))

    report = process_offline_team_season_sources(
        [
            OfflineTeamSeasonSource.from_url(missing_url),
            OfflineTeamSeasonSource.from_url(cached_url),
        ],
        cache=cache,
    )

    assert [entry.status for entry in report.entries] == ["failed", "validated"]
    assert report.failed_entries == 1
    assert report.validated_entries == 1
    assert "Cached HTML file not found" in str(report.entries[0].error_message)
    assert report.entries[1].source.team_abbreviation == "DEN"


@pytest.mark.unit
def test_validation_errors_are_actionable_and_do_not_return_invalid_rows(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    url = build_team_season_url("BOS", 2024)
    _write_gzip(cache.path_for_url(url), MINIMAL_FIXTURE.read_text(encoding="utf-8"))

    report = process_offline_team_season_sources(
        [OfflineTeamSeasonSource.from_url(url)],
        cache=cache,
    )

    entry = report.entries[0]
    assert entry.status == "failed"
    assert entry.normalized_rows == ()
    assert "Validation failed" in str(entry.error_message)
    assert {issue.code for issue in entry.validation_issues} == {"missing_player_id"}
    assert entry.validation_issues[0].source_table == "roster"


@pytest.mark.unit
def test_explicit_path_outside_cache_root_fails_without_stopping_other_inputs(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    outside_path = tmp_path / "outside.html.gz"
    valid_path = cache.root_dir / "basketball-reference" / "fixture.html.gz"
    html = PHASE3_FIXTURE.read_text(encoding="utf-8")
    _write_gzip(outside_path, html)
    _write_gzip(valid_path, html)

    report = process_offline_team_season_sources(
        [
            OfflineTeamSeasonSource.from_path(
                outside_path,
                team_abbreviation="BOS",
                season_year=2024,
            ),
            OfflineTeamSeasonSource.from_path(
                valid_path,
                team_abbreviation="DEN",
                season_year=2023,
            ),
        ],
        cache=cache,
    )

    assert [entry.status for entry in report.entries] == ["failed", "validated"]
    assert "must stay under cache root" in str(report.entries[0].error_message)
    assert report.entries[1].source.team_abbreviation == "DEN"


@pytest.mark.unit
def test_url_source_must_be_explicit_team_season_page() -> None:
    with pytest.raises(ValueError, match="team-season URL"):
        OfflineTeamSeasonSource.from_url(build_team_season_games_url("BOS", 2024))


@pytest.mark.unit
def test_processing_order_is_gzip_parse_normalize_validate(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    cache = HtmlCache(tmp_path / "cache")
    source = OfflineTeamSeasonSource.from_path(
        cache.root_dir / "fixture.html.gz",
        team_abbreviation="BOS",
        season_year=2024,
    )

    def fake_read_cached_gzip(path: Path) -> str:
        calls.append("read")
        return "<html></html>"

    def fake_parse_team_season_page(html: str) -> dict[str, list[dict[str, str]]]:
        calls.append("parse")
        return {"totals": [{"player": "Jayson Tatum"}]}

    def fake_normalize_team_season_page(
        parsed: dict[str, list[dict[str, str]]],
        *,
        team_abbreviation: str,
        season_year: int,
    ) -> list[dict[str, object]]:
        calls.append("normalize")
        assert parsed == {"totals": [{"player": "Jayson Tatum"}]}
        assert team_abbreviation == "BOS"
        assert season_year == 2024
        return [_valid_row()]

    def fake_validate_normalized_team_season_rows(
        rows: list[dict[str, object]],
        *,
        required_tables: set[str] | None = None,
        require_stable_player_id: bool = True,
    ) -> list[object]:
        calls.append("validate")
        assert rows == [_valid_row()]
        assert required_tables == {"totals"}
        assert require_stable_player_id is True
        return []

    monkeypatch.setattr(offline_processor, "_read_cached_gzip", fake_read_cached_gzip)
    monkeypatch.setattr(offline_processor, "parse_team_season_page", fake_parse_team_season_page)
    monkeypatch.setattr(
        offline_processor,
        "normalize_team_season_page",
        fake_normalize_team_season_page,
    )
    monkeypatch.setattr(
        offline_processor,
        "validate_normalized_team_season_rows",
        fake_validate_normalized_team_season_rows,
    )

    report = process_offline_team_season_sources(
        [source],
        cache=cache,
        required_tables={"totals"},
    )

    assert calls == ["read", "parse", "normalize", "validate"]
    assert report.entries[0].status == "validated"


@pytest.mark.unit
def test_bounded_local_workers_preserve_input_order(tmp_path) -> None:
    cache = HtmlCache(tmp_path)
    urls = [build_team_season_url("BOS", 2024), build_team_season_url("DEN", 2023)]
    html = PHASE3_FIXTURE.read_text(encoding="utf-8")
    for url in urls:
        _write_gzip(cache.path_for_url(url), html)

    report = process_offline_team_season_sources(
        [OfflineTeamSeasonSource.from_url(url) for url in urls],
        cache=cache,
        max_workers=2,
    )

    assert [entry.source.team_abbreviation for entry in report.entries] == ["BOS", "DEN"]
    assert [entry.status for entry in report.entries] == ["validated", "validated"]


@pytest.mark.unit
def test_processor_does_not_accept_or_import_network_boundaries() -> None:
    signature = inspect.signature(process_offline_team_season_sources)
    module_source = inspect.getsource(offline_processor)

    assert "client" not in signature.parameters
    assert "BasketballReferenceClient" not in module_source
    assert "import requests" not in module_source
    assert "import httpx" not in module_source


def _write_gzip(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        file.write(html)


def _valid_row() -> dict[str, object]:
    return {
        "league": "NBA",
        "season_year": 2024,
        "team_abbreviation": "BOS",
        "team_context": "team",
        "source_table": "totals",
        "stat_scope": "player_team_season",
        "player_name": "Jayson Tatum",
        "basketball_reference_player_id": "tatumja01",
        "stable_player_key": "tatumja01",
        "identifier_status": "present",
        "values": {"games": 74},
    }
