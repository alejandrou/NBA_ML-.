from pathlib import Path

import pytest

from nba_data.scraping.normalizers.team_season import normalize_team_season_page
from nba_data.scraping.parsers.team_season import parse_team_season_page

FIXTURE = Path("tests/fixtures/html/team_season_phase3.html")
TEAM_NAME_FIXTURE = Path("tests/fixtures/html/team_season_bos_2000_h1.html")


@pytest.mark.unit
def test_normalize_team_season_page_adds_context_and_preserves_player_id() -> None:
    parsed = parse_team_season_page(FIXTURE.read_text(encoding="utf-8"))

    rows = normalize_team_season_page(parsed, team_abbreviation="bos", season_year=2024)

    per_game = _first(rows, "per_game")
    assert per_game["league"] == "NBA"
    assert per_game["season_year"] == 2024
    assert per_game["team_abbreviation"] == "BOS"
    assert per_game["team_context"] == "team"
    assert per_game["source_table"] == "per_game"
    assert per_game["stat_scope"] == "player_team_season"
    assert per_game["player_name"] == "Jayson Tatum"
    assert per_game["basketball_reference_player_id"] == "tatumja01"
    assert per_game["stable_player_key"] == "tatumja01"
    assert per_game["identifier_status"] == "present"


@pytest.mark.unit
def test_normalize_team_season_page_converts_safe_numbers_only() -> None:
    parsed = parse_team_season_page(FIXTURE.read_text(encoding="utf-8"))

    rows = normalize_team_season_page(parsed, team_abbreviation="BOS", season_year=2024)

    totals = _first(rows, "totals")
    assert totals["values"]["games"] == 74
    assert totals["values"]["fg_pct"] == 0.471
    assert totals["values"]["pts"] == 1987
    assert totals["values"]["name_display"] == "Jayson Tatum"


@pytest.mark.unit
def test_normalize_team_season_page_classifies_roster_scope() -> None:
    parsed = parse_team_season_page(FIXTURE.read_text(encoding="utf-8"))

    rows = normalize_team_season_page(parsed, team_abbreviation="BOS", season_year=2024)

    roster = _first(rows, "roster")
    assert roster["stat_scope"] == "team_roster"
    assert roster["values"]["number"] == 0
    assert roster["values"]["pos"] == "SF"


@pytest.mark.unit
def test_normalize_team_season_page_treats_tot_as_aggregate() -> None:
    parsed = {
        "totals": [
            {
                "name_display": "Traded Player",
                "basketball_reference_player_id": "tradepl01",
                "team_abbreviation": "TOT",
                "games": "82",
            }
        ]
    }

    rows = normalize_team_season_page(parsed, team_abbreviation="BOS", season_year=2024)

    assert rows[0]["team_abbreviation"] == "TOT"
    assert rows[0]["team_context"] == "aggregate"
    assert rows[0]["stat_scope"] == "player_season_aggregate"


@pytest.mark.unit
def test_normalize_team_season_page_marks_missing_player_id_as_debt() -> None:
    parsed = {"totals": [{"name_display": "Missing Id", "games": "1"}]}

    rows = normalize_team_season_page(parsed, team_abbreviation="BOS", season_year=2024)

    assert rows[0]["player_name"] == "Missing Id"
    assert rows[0]["basketball_reference_player_id"] is None
    assert rows[0]["stable_player_key"] is None
    assert rows[0]["identifier_status"] == "missing_player_id"


@pytest.mark.unit
def test_parser_and_normalizer_remain_separate_steps() -> None:
    html = FIXTURE.read_text(encoding="utf-8")

    parsed = parse_team_season_page(html)
    rows = normalize_team_season_page(parsed, team_abbreviation="BOS", season_year=2024)

    assert "league" not in parsed["per_game"][0]
    assert "values" in rows[0]


@pytest.mark.unit
def test_normalizer_carries_team_name_metadata_without_mixing_it_into_stat_rows() -> None:
    parsed = parse_team_season_page(TEAM_NAME_FIXTURE.read_text(encoding="utf-8"))

    rows = normalize_team_season_page(parsed, team_abbreviation="BOS", season_year=2000)

    assert rows.team_name == "Boston Celtics"
    assert rows.team_name_issues == ()
    assert all("team_name" not in row for row in rows)


def _first(rows: list[dict[str, object]], source_table: str) -> dict[str, object]:
    return next(row for row in rows if row["source_table"] == source_table)
