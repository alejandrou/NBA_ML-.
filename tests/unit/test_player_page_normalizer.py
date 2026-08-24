from pathlib import Path

import pytest

from nba_data.scraping.normalizers.player_page import (
    is_did_not_play_placeholder,
    normalize_player_page_postseason,
    normalize_player_page_regular_season,
    season_end_year,
)
from nba_data.scraping.parsers.player_page import (
    parse_player_page_postseason,
    parse_player_page_regular_season,
)

REGULAR_FIXTURE = Path("tests/fixtures/html/player_page_harden_regular_season.html")
POSTSEASON_FIXTURE = Path("tests/fixtures/html/player_page_harden_postseason.html")
MILLER_FIXTURE = Path("tests/fixtures/html/player_page_miller_did_not_play.html")
MCGRATH_FIXTURE = Path("tests/fixtures/html/player_page_mcgrath_did_not_play.html")

DID_NOT_PLAY_REASONS = (
    "Did not play -",
    "Did not play - COVID-19",
    "Did not play - coaching staff",
    "Did not play - contract bought out",
    "Did not play - contractual issues",
    "Did not play - dropped from roster",
    "Did not play - holdout/back injury",
    "Did not play - illness",
    "Did not play - injury",
    "Did not play - legal",
    "Did not play - medical condition",
    "Did not play - mental health",
    "Did not play - military service",
    "Did not play - other",
    "Did not play - other pro league",
    "Did not play - rehab",
    "Did not play - retired",
    "Did not play - retired/MiLB",
    "Did not play - sat out",
    "Did not play - suspended",
    "Did not play - unsigned",
    "Did not play - waived",
)

# The archive opens on `1999-00`, the one label in it that crosses a century.
ARCHIVE_SEASON_LABELS = tuple(
    (f"{start}-{(start + 1) % 100:02d}", start + 1) for start in range(1999, 2025)
)


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
@pytest.mark.parametrize("reason", DID_NOT_PLAY_REASONS)
def test_did_not_play_placeholder_predicate_matches_all_cache_reasons(reason: str) -> None:
    row = {"year_id": "2003-04", "age": reason}

    assert is_did_not_play_placeholder(row)
    assert not is_did_not_play_placeholder({**row, "team_id": "MIN"})


@pytest.mark.unit
def test_missing_team_row_without_did_not_play_reason_remains_unselectable() -> None:
    result = normalize_player_page_regular_season(
        {
            "totals": [
                {"year_id": "2003-04", "age": "33", "games": "48", "pts": "121"},
            ]
        },
        basketball_reference_player_id="example01",
    )

    assert result.rows_selected == 0
    assert result.selection_entries[0].reason == "no_supported_team_row"


@pytest.mark.unit
def test_did_not_play_only_season_has_distinct_selection_reason() -> None:
    result = normalize_player_page_regular_season(
        {
            "totals": [
                {"year_id": "2003-04", "age": "Did not play - injury"},
            ]
        },
        basketball_reference_player_id="example01",
    )

    assert result.rows_selected == 0
    assert result.selection_entries[0].reason == "did_not_play_season"
    assert result.selection_entries[0].reason not in {
        "selected_single_team_row",
        "no_supported_team_row",
    }


@pytest.mark.unit
def test_miller_fixture_selects_real_rows_and_never_emits_placeholder_values() -> None:
    parsed = parse_player_page_regular_season(MILLER_FIXTURE.read_text(encoding="utf-8"))

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="milleol01",
    )

    assert result.rows_selected == 8
    assert {row["source_team_code"] for row in result.selected_rows} == {"MIN"}
    assert {row["season_year"] for row in result.selected_rows} == {2004}
    assert {(row["values"]["games"], row["values"]["pts"]) for row in result.selected_rows} == {
        (48, 121)
    }
    assert all(
        not any(
            isinstance(value, str) and value.startswith("Did not play -")
            for value in row["values"].values()
        )
        for row in result.selected_rows
    )


@pytest.mark.unit
def test_mcgrath_fixture_keeps_postseason_rows_and_drops_regular_placeholder_rows() -> None:
    html = MCGRATH_FIXTURE.read_text(encoding="utf-8")

    regular_result = normalize_player_page_regular_season(
        parse_player_page_regular_season(html),
        basketball_reference_player_id="mcgratr01",
    )
    postseason_result = normalize_player_page_postseason(
        parse_player_page_postseason(html),
        basketball_reference_player_id="mcgratr01",
    )

    assert regular_result.rows_selected == 0
    assert {entry.reason for entry in regular_result.selection_entries} == {"did_not_play_season"}
    assert postseason_result.rows_selected == 16
    assert {row["season_year"] for row in postseason_result.selected_rows} == {2013}
    aggregate_rows = [
        row
        for row in postseason_result.selected_rows
        if row["stat_scope"] == "player_postseason_aggregate"
    ]
    team_rows = [
        row
        for row in postseason_result.selected_rows
        if row["stat_scope"] == "player_team_postseason"
    ]
    assert len(aggregate_rows) == 8
    assert len(team_rows) == 8
    assert {row["source_team_code"] for row in aggregate_rows} == {"SAS"}
    assert {row["team_abbreviation"] for row in team_rows} == {"SAS"}


@pytest.mark.unit
def test_normalize_player_page_regular_season_supports_real_cache_column_aliases() -> None:
    parsed = {
        "totals": [
            {"year_id": "2020-21", "team_name_abbr": "2TM", "comp_name_abbr": "NBA", "games": "44", "pts": "1083"},
            {"year_id": "2020-21", "team_name_abbr": "HOU", "comp_name_abbr": "NBA", "games": "8", "pts": "199"},
            {"year_id": "2020-21", "team_name_abbr": "BRK", "comp_name_abbr": "NBA", "games": "36", "pts": "884"},
        ],
    }

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="hardeja01",
    )

    assert result.rows_selected == 1
    assert result.rows_skipped == 2
    assert result.selected_rows[0]["season_year"] == 2021
    assert result.selected_rows[0]["source_team_code"] == "2TM"
    assert result.selected_rows[0]["values"] == {"games": 44, "pts": 1083}


@pytest.mark.unit
def test_normalize_player_page_regular_season_drops_pos_for_totals_and_per_poss() -> None:
    parsed = {
        "totals": [
            {"year_id": "2020-21", "team_name_abbr": "2TM", "pos": "C", "games": "44", "pts": "1083"},
        ],
        "per_poss": [
            {"year_id": "2020-21", "team_name_abbr": "2TM", "pos": "C", "games": "44", "mp": "1592", "pts_per_poss": "36.2"},
        ],
        "advanced": [
            {"year_id": "2020-21", "team_name_abbr": "2TM", "pos": "C", "games": "44", "mp": "1592", "per": "25.0"},
        ],
    }

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="example01",
    )

    values_by_table = {row["source_table"]: row["values"] for row in result.selected_rows}
    assert "pos" not in values_by_table["totals"]
    assert "pos" not in values_by_table["per_poss"]
    assert values_by_table["advanced"]["pos"] == "C"


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


@pytest.mark.unit
def test_normalize_player_page_postseason_supports_real_cache_column_aliases() -> None:
    parsed = {
        "totals": [
            {"year_id": "2020-21", "team_name_abbr": "2TM", "comp_name_abbr": "NBA", "games": "10", "pts": "201"},
            {"year_id": "2020-21", "team_name_abbr": "BRK", "comp_name_abbr": "NBA", "games": "9", "pts": "180"},
            {"year_id": "2020-21", "team_name_abbr": "TOT", "comp_name_abbr": "NBA", "games": "10", "pts": "201"},
        ],
    }

    result = normalize_player_page_postseason(
        parsed,
        basketball_reference_player_id="hardeja01",
    )

    aggregate_rows = [row for row in result.selected_rows if row["stat_scope"] == "player_postseason_aggregate"]
    team_rows = [row for row in result.selected_rows if row["stat_scope"] == "player_team_postseason"]

    assert len(aggregate_rows) == 1
    assert aggregate_rows[0]["season_year"] == 2021
    assert aggregate_rows[0]["source_team_code"] == "2TM"
    assert aggregate_rows[0]["values"] == {"games": 10, "pts": 201}
    assert len(team_rows) == 1
    assert team_rows[0]["team_abbreviation"] == "BRK"
    assert team_rows[0]["values"] == {"games": 9, "pts": 180}


@pytest.mark.unit
@pytest.mark.parametrize(("label", "expected"), ARCHIVE_SEASON_LABELS)
@pytest.mark.parametrize("key", ["season", "year_id"])
def test_season_end_year_covers_every_archive_label(key: str, label: str, expected: int) -> None:
    assert season_end_year({key: label}) == expected


@pytest.mark.unit
def test_archive_season_labels_span_the_full_archive_range() -> None:
    labels = [label for label, _ in ARCHIVE_SEASON_LABELS]

    assert len(labels) == 26
    assert labels[0] == "1999-00"
    assert labels[-1] == "2024-25"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("label", "expected"),
    [
        # The century-crossing label the archive opens on.
        ("1999-00", 2000),
        # The same season written in the four-digit form.
        ("1999-2000", 2000),
        # A plain four-digit season year, not a range.
        ("2000", 2000),
        # A label that does not cross a century.
        ("2000-01", 2001),
        # The archive's current final label.
        ("2024-25", 2025),
        # The rule is a comparison, not a hard-coded 1900/2000 pivot.
        ("2099-00", 2100),
        ("2099-2100", 2100),
        ("1899-00", 1900),
    ],
)
def test_season_end_year_resolves_boundary_forms(label: str, expected: int) -> None:
    assert season_end_year({"season": label}) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "label",
    [
        "",
        "   ",
        "99-00",
        "2020-",
        "2020-2",
        "2020-021",
        "2020/21",
        "20202021",
        "Career",
        "2020-21 (partial)",
    ],
)
def test_season_end_year_returns_none_for_malformed_labels(label: str) -> None:
    assert season_end_year({"season": label}) is None


@pytest.mark.unit
def test_season_end_year_returns_none_when_no_season_key_is_present() -> None:
    assert season_end_year({"team_id": "BOS", "games": "70"}) is None


@pytest.mark.unit
def test_normalize_player_page_regular_season_resolves_century_crossing_season() -> None:
    parsed = {
        "totals": [
            {"season": "1999-00", "team_id": "LAL", "games": "82", "pts": "2344"},
        ],
    }

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="oneassh01",
    )

    assert result.rows_selected == 1
    assert result.selected_rows[0]["season_year"] == 2000


@pytest.mark.unit
def test_normalize_player_page_postseason_resolves_century_crossing_season() -> None:
    parsed = {
        "totals": [
            {"year_id": "1999-00", "team_name_abbr": "LAL", "games": "23", "pts": "707"},
        ],
    }

    result = normalize_player_page_postseason(
        parsed,
        basketball_reference_player_id="oneassh01",
    )

    assert {row["season_year"] for row in result.selected_rows} == {2000}


# Bobby Jones's 2007-08 season is the one `5TM` in the cached archive. It was
# lost outright while the marker set was the literal `{2TM, 3TM, 4TM}`: the
# season yielded zero aggregate rows instead of one per source table.
AGGREGATE_SOURCE_TABLES = (
    "totals",
    "per_game",
    "per_minute",
    "per_poss",
    "advanced",
    "shooting",
    "adj_shooting",
    "pbp",
)
BOBBY_JONES_TEAMS = ("DEN", "MEM", "HOU", "SAS", "DAL")


def _bobby_jones_2008_parsed() -> dict[str, list[dict[str, str]]]:
    return {
        source_table: [
            {"season": "2007-08", "team_id": "5TM", "games": "50", "pts": "185"},
            *(
                {"season": "2007-08", "team_id": team, "games": "10", "pts": "37"}
                for team in BOBBY_JONES_TEAMS
            ),
        ]
        for source_table in AGGREGATE_SOURCE_TABLES
    }


@pytest.mark.unit
def test_normalize_player_page_regular_season_selects_a_five_team_aggregate_row() -> None:
    result = normalize_player_page_regular_season(
        _bobby_jones_2008_parsed(),
        basketball_reference_player_id="jonesbo02",
    )

    assert result.rows_selected == 8
    assert {row["season_year"] for row in result.selected_rows} == {2008}
    assert {row["source_team_code"] for row in result.selected_rows} == {"5TM"}
    assert all(row["team_abbreviation"] is None for row in result.selected_rows)


@pytest.mark.unit
@pytest.mark.parametrize("marker", ["2TM", "3TM", "4TM", "5TM", "6TM", "10TM"])
def test_normalize_player_page_regular_season_selects_any_multi_team_marker(marker: str) -> None:
    parsed = {
        "totals": [
            {"season": "2007-08", "team_id": marker, "games": "50", "pts": "185"},
            {"season": "2007-08", "team_id": "DEN", "games": "10", "pts": "37"},
            {"season": "2007-08", "team_id": "MEM", "games": "10", "pts": "37"},
        ],
    }

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="jonesbo02",
    )

    assert result.rows_selected == 1
    assert result.selected_rows[0]["source_team_code"] == marker


@pytest.mark.unit
@pytest.mark.parametrize("value", ["0TM", "1TM", "02TM"])
def test_normalize_player_page_regular_season_does_not_treat_near_markers_as_aggregates(
    value: str,
) -> None:
    parsed = {
        "totals": [
            {"season": "2007-08", "team_id": value, "games": "50", "pts": "185"},
            {"season": "2007-08", "team_id": "DEN", "games": "10", "pts": "37"},
        ],
    }

    result = normalize_player_page_regular_season(
        parsed,
        basketball_reference_player_id="jonesbo02",
    )

    # Two real-looking team rows and no marker: the season is ambiguous, not aggregated.
    assert result.rows_selected == 0
    assert result.selection_entries[0].reason == "ambiguous_multiple_real_team_rows"
