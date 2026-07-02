from pathlib import Path

import pytest

from nba_data.scraping.normalizers.player_page import (
    normalize_player_page_postseason,
    normalize_player_page_regular_season,
)
from nba_data.scraping.parsers.player_page import (
    parse_player_page_postseason,
    parse_player_page_regular_season,
)

REGULAR_FIXTURE = Path("tests/fixtures/html/player_page_harden_regular_season.html")
POSTSEASON_FIXTURE = Path("tests/fixtures/html/player_page_harden_postseason.html")


@pytest.mark.unit
def test_normalize_player_page_regular_season_selects_multi_team_row_only() -> None:
    parsed = parse_player_page_regular_season(REGULAR_FIXTURE.read_text(encoding="utf-8"))

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="hardeja01",
    )

    assert result.tables_parsed >= 3
    assert result.rows_selected == 8
    assert all(row["season_year"] == 2021 for row in result.selected_rows)
    assert all(row["source_team_code"] == "2TM" for row in result.selected_rows)
    assert all(row["basketball_reference_player_id"] == "hardeja01" for row in result.selected_rows)
    assert result.rows_skipped >= 6


@pytest.mark.unit
def test_normalize_player_page_regular_season_selects_single_real_team_row_when_no_multi_team_marker() -> None:
    parsed = {
        "totals": [
            {"season": "2023-24", "team_id": "BOS", "games": "70", "pts": "1620"},
        ],
        "per_game": [
            {"season": "2023-24", "team_id": "BOS", "games": "70", "pts_per_g": "23.1"},
        ],
        "advanced": [
            {"season": "2023-24", "team_id": "BOS", "games": "70", "mp": "2486", "per": "19.1"},
        ],
    }

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="brownja02",
    )

    assert result.rows_selected == 3
    assert {row["source_team_code"] for row in result.selected_rows} == {"BOS"}
    assert {row["season_year"] for row in result.selected_rows} == {2024}


@pytest.mark.unit
def test_normalize_player_page_regular_season_never_selects_tot() -> None:
    parsed = {
        "totals": [
            {"season": "2023-24", "team_id": "TOT", "games": "82", "pts": "1000"},
        ]
    }

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="example01",
    )

    assert result.rows_selected == 0
    assert result.rows_skipped == 1
    assert all(entry.source_team_code != "TOT" for entry in result.selection_entries)


@pytest.mark.unit
def test_normalize_player_page_postseason_selects_aggregate_and_team_rows_for_single_team_playoffs() -> None:
    parsed = parse_player_page_postseason(POSTSEASON_FIXTURE.read_text(encoding="utf-8"))

    result = normalize_player_page_postseason(
        parsed,
        basketball_reference_player_id="hardeja01",
    )

    aggregate_rows = [row for row in result.selected_rows if row["stat_scope"] == "player_postseason_aggregate"]
    team_rows = [row for row in result.selected_rows if row["stat_scope"] == "player_team_postseason"]

    assert result.tables_parsed == 3
    assert len(aggregate_rows) == 3
    assert len(team_rows) == 3
    assert {row["source_team_code"] for row in aggregate_rows} == {"BRK"}
    assert {row["team_abbreviation"] for row in team_rows} == {"BRK"}


@pytest.mark.unit
def test_normalize_player_page_postseason_loads_synthetic_only_for_aggregate_and_skips_tot() -> None:
    parsed = {
        "totals": [
            {"season": "2020-21", "team_id": "2TM", "games": "10", "pts": "201"},
            {"season": "2020-21", "team_id": "BRK", "games": "9", "pts": "180"},
            {"season": "2020-21", "team_id": "TOT", "games": "10", "pts": "201"},
        ],
    }

    result = normalize_player_page_postseason(
        parsed,
        basketball_reference_player_id="hardeja01",
    )

    aggregate_rows = [row for row in result.selected_rows if row["stat_scope"] == "player_postseason_aggregate"]
    team_rows = [row for row in result.selected_rows if row["stat_scope"] == "player_team_postseason"]

    assert len(aggregate_rows) == 1
    assert aggregate_rows[0]["source_team_code"] == "2TM"
    assert len(team_rows) == 1
    assert team_rows[0]["team_abbreviation"] == "BRK"
    assert result.unsupported_rows == 1
