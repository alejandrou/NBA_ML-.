from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from nba_data.scraping.parsers.league_schedule import parse_league_schedule_page

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"


def _page(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _may_2021() -> str:
    return _page("league_schedule_2021_may_trimmed.html")


@pytest.mark.unit
def test_a_played_row_carries_its_id_teams_points_and_context() -> None:
    parsed = parse_league_schedule_page(_may_2021())

    last_regular = parsed.games[0]
    assert parsed.issues == ()
    assert last_regular.game_id == "202105160SAC"
    assert last_regular.game_date == date(2021, 5, 16)
    assert (last_regular.visitor_code, last_regular.visitor_name, last_regular.visitor_points) == (
        "UTA",
        "Utah Jazz",
        121,
    )
    assert (last_regular.home_code, last_regular.home_points) == ("SAC", 99)
    assert last_regular.start_time == "9:00p"
    assert last_regular.game_duration == "2:05"
    assert last_regular.arena == "Golden 1 Center"
    assert last_regular.overtime_periods == 0
    assert last_regular.played is True


@pytest.mark.unit
def test_only_play_in_games_are_marked_and_playoff_games_are_not() -> None:
    games = {game.game_id: game for game in parse_league_schedule_page(_may_2021()).games}

    assert games["202105180IND"].play_in is True
    assert games["202105180IND"].notes == "Play-In Game"
    # The first 2021 playoff game: no separator row and no note on the real page.
    assert games["202105220MIL"].play_in is False
    assert games["202105220MIL"].notes is None
    assert games["202105160SAC"].play_in is False


@pytest.mark.unit
def test_overtime_markers_become_period_counts() -> None:
    games = {game.game_id: game for game in parse_league_schedule_page(_may_2021()).games}

    assert games["202105220MIL"].overtime_periods == 1


@pytest.mark.unit
def test_blank_attendance_stays_unknown_and_zero_stays_zero() -> None:
    bubble = parse_league_schedule_page(_page("league_schedule_2020_july_trimmed.html")).games

    assert [(game.game_id, game.attendance) for game in bubble] == [
        ("202007300NOP", None),
        ("202007310BRK", 0),
    ]
    assert {game.arena for game in bubble} == {"HP Field House"}


@pytest.mark.unit
def test_month_links_keep_the_two_october_pages_of_2019_20() -> None:
    parsed = parse_league_schedule_page(_page("league_schedule_2020_july_trimmed.html"))

    assert parsed.month_links == (
        "october-2019",
        "november",
        "december",
        "january",
        "february",
        "march",
        "july",
        "august",
        "september",
        "october-2020",
    )


@pytest.mark.unit
def test_upcoming_games_have_no_id_no_points_and_keep_their_notes() -> None:
    parsed = parse_league_schedule_page(_page("league_schedule_2027_trimmed.html"))

    assert parsed.issues == ()
    assert [game.played for game in parsed.games] == [False, False, False]
    assert all(game.game_id is None for game in parsed.games)
    assert all(game.visitor_points is None and game.home_points is None for game in parsed.games)
    opener = parsed.games[0]
    assert (opener.game_date, opener.visitor_code, opener.home_code) == (
        date(2026, 10, 20),
        "BOS",
        "DET",
    )
    assert parsed.games[-1].notes == "NBA Cup"


@pytest.mark.unit
def test_a_page_without_the_schedule_table_reports_it() -> None:
    parsed = parse_league_schedule_page("<html><body><p>Page not found</p></body></html>")

    assert parsed.games == ()
    assert [issue.code for issue in parsed.issues] == ["schedule_table_missing"]


@pytest.mark.unit
def test_a_box_score_id_that_disagrees_with_its_row_is_reported() -> None:
    html = _may_2021().replace("/boxscores/202105160SAC.html", "/boxscores/202105160UTA.html")

    parsed = parse_league_schedule_page(html)

    assert [issue.code for issue in parsed.issues] == ["schedule_game_id_mismatch"]


@pytest.mark.unit
def test_an_unknown_overtime_marker_is_reported_not_guessed() -> None:
    html = _may_2021().replace('data-stat="overtimes">OT<', 'data-stat="overtimes">XOT<')

    parsed = parse_league_schedule_page(html)

    assert [issue.code for issue in parsed.issues] == ["schedule_overtime_unreadable"]
