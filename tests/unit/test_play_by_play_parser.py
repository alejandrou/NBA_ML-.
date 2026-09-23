from __future__ import annotations

from pathlib import Path

import pytest

from nba_data.scraping.parsers.play_by_play import (
    SIDE_GAME,
    SIDE_HOME,
    SIDE_VISITOR,
    parse_play_by_play_page,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"


def _play_by_play() -> str:
    return (FIXTURES / "play_by_play_202008170DEN_trimmed.html").read_text(encoding="utf-8")


@pytest.mark.unit
def test_events_keep_feed_order_sides_scores_and_player_links() -> None:
    parsed = parse_play_by_play_page(_play_by_play())

    assert parsed.issues == ()
    assert [event.sequence for event in parsed.events] == list(range(1, len(parsed.events) + 1))
    jump_ball = parsed.events[0]
    assert (jump_ball.period, jump_ball.side) == (1, SIDE_GAME)
    assert jump_ball.player_ids == ("goberru01", "jokicni01", "millspa01")
    three = parsed.events[7]
    assert (three.side, three.points) == (SIDE_VISITOR, 3)
    assert (three.visitor_score, three.home_score) == (3, 0)
    assert three.player_ids == ("onealro01", "mitchdo01")
    answer = parsed.events[8]
    assert (answer.side, answer.points, answer.home_score) == (SIDE_HOME, 2, 2)


@pytest.mark.unit
def test_a_foul_sits_in_the_column_of_the_team_that_drew_it() -> None:
    """Real layout: the column is not always the first-named player's team."""

    foul = parse_play_by_play_page(_play_by_play()).events[12]

    assert foul.description.startswith("Shooting foul by N. Jokić")
    assert foul.side == SIDE_VISITOR
    assert foul.player_ids == ("jokicni01", "inglejo01")


@pytest.mark.unit
def test_same_clock_substitutions_stay_separate_and_ordered() -> None:
    parsed = parse_play_by_play_page(_play_by_play())

    substitutions = [event for event in parsed.events if "enters the game for" in event.description]
    assert [(event.clock, event.side) for event in substitutions] == [
        ("4:43.0", SIDE_VISITOR),
        ("4:43.0", SIDE_HOME),
    ]
    assert substitutions[0].player_ids == ("niangge01", "inglejo01")


@pytest.mark.unit
def test_overtime_is_period_five_and_the_final_score_is_read() -> None:
    parsed = parse_play_by_play_page(_play_by_play())

    assert parsed.periods == 5
    assert parsed.final_score == (125, 135)
    start = next(event for event in parsed.events if event.description == "Start of 1st overtime")
    assert (start.period, start.clock) == (5, "5:00.0")
    assert parsed.events[-1].description == "End of 1st overtime"


@pytest.mark.unit
def test_overtime_points_come_from_the_score_column() -> None:
    parsed = parse_play_by_play_page(_play_by_play())

    # The fixture keeps the last scoring event of regulation (115-115) and all of
    # overtime, so the overtime period is complete: Utah 10, Denver 20.
    assert parsed.points_by_period()[5] == (10, 20)


@pytest.mark.unit
def test_replay_reviews_and_team_events_are_kept() -> None:
    parsed = parse_play_by_play_page(_play_by_play())
    descriptions = [event.description for event in parsed.events]

    assert "Instant Replay (Request: Ruling Stands)" in descriptions
    violation = next(
        event for event in parsed.events if event.description.startswith("Violation by Team")
    )
    assert violation.player_ids == ()
    assert violation.points == 0


@pytest.mark.unit
def test_clock_readings_become_seconds_remaining() -> None:
    by_clock = {
        event.clock: event.seconds_remaining
        for event in parse_play_by_play_page(_play_by_play()).events
    }

    assert by_clock["11:40.0"] == 700.0
    assert by_clock["5:00.0"] == 300.0
    assert by_clock["0:00.0"] == 0.0


@pytest.mark.unit
def test_a_page_without_the_table_reports_it() -> None:
    parsed = parse_play_by_play_page("<html><body></body></html>")

    assert parsed.events == ()
    assert parsed.final_score is None
    assert [issue.code for issue in parsed.issues] == ["play_by_play_table_missing"]


@pytest.mark.unit
def test_a_row_with_events_on_both_sides_is_reported() -> None:
    real_row = '<td class="center">117-126</td><td>\xa0</td><td>\xa0</td>'
    both_sides = '<td class="center">117-126</td><td>\xa0</td><td>Denver full timeout</td>'
    html = _play_by_play()
    assert html.count(real_row) == 1

    parsed = parse_play_by_play_page(html.replace(real_row, both_sides))

    assert [issue.code for issue in parsed.issues] == ["event_row_unreadable"]
