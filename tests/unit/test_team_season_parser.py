from pathlib import Path

import pytest

from nba_data.scraping.parsers.team_season import parse_roster, parse_team_season_page

FIXTURE = Path("tests/fixtures/html/team_season_minimal.html")
REALISTIC_FIXTURE = Path("tests/fixtures/html/team_season_realistic.html")


@pytest.mark.unit
def test_parse_team_season_page_reads_visible_and_commented_tables() -> None:
    html = FIXTURE.read_text(encoding="utf-8")

    parsed = parse_team_season_page(html)

    assert parsed["roster"] == [{"No.": "0", "Player": "Jayson Tatum", "Pos": "SF"}]
    assert parsed["totals"] == [{"player": "Jayson Tatum", "g": "74", "pts": "1987"}]
    assert parsed["advanced"] == [{"player": "Jayson Tatum", "per": "22.3"}]


@pytest.mark.unit
def test_parse_team_season_page_reads_realistic_commented_wrapped_tables() -> None:
    html = REALISTIC_FIXTURE.read_text(encoding="utf-8")

    parsed = parse_team_season_page(html)

    assert parsed["roster"] == [
        {
            "number": "0",
            "player": "Jayson Tatum",
            "pos": "SF",
            "height": "6-8",
            "weight": "210",
        },
        {
            "number": "7",
            "player": "Jaylen Brown",
            "pos": "SG",
            "height": "6-6",
            "weight": "223",
        },
    ]
    assert [row["player"] for row in parsed["totals"]] == [
        "Jayson Tatum",
        "Jaylen Brown",
    ]
    assert [row["pts"] for row in parsed["totals"]] == ["1987", "1644"]
    assert [row["player"] for row in parsed["advanced"]] == [
        "Jayson Tatum",
        "Jaylen Brown",
    ]
    assert [row["per"] for row in parsed["advanced"]] == ["22.3", "19.1"]


@pytest.mark.unit
def test_parse_roster_is_pure_helper() -> None:
    html = FIXTURE.read_text(encoding="utf-8")

    assert parse_roster(html)[0]["Player"] == "Jayson Tatum"
