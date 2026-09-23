from __future__ import annotations

from pathlib import Path

import pytest

from nba_data.scraping.parsers.box_score import (
    COUNTING_STATS,
    GAME_TYPE_CUP_FINAL,
    GAME_TYPE_PLAY_IN,
    GAME_TYPE_PLAYOFFS,
    GAME_TYPE_REGULAR_SEASON,
    GAME_TYPE_UNKNOWN,
    PARTICIPATION_DID_NOT_PLAY,
    PARTICIPATION_PLAYED,
    parse_box_score_page,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"


def _page(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _bubble_playoff() -> str:
    return _page("box_score_202008170DEN_trimmed.html")


@pytest.mark.unit
def test_scorebox_orders_visitor_then_home_and_reads_the_venue() -> None:
    parsed = parse_box_score_page(_bubble_playoff())

    assert parsed.issues == ()
    assert parsed.visitor is not None and parsed.home is not None
    assert (parsed.visitor.code, parsed.visitor.name, parsed.visitor.scorebox_points) == (
        "UTA",
        "Utah Jazz",
        125,
    )
    assert (parsed.home.code, parsed.home.name, parsed.home.scorebox_points) == (
        "DEN",
        "Denver Nuggets",
        135,
    )
    assert parsed.venue == "HP Field House, Bay Lake, Florida"
    assert parsed.play_by_play_linked is True


@pytest.mark.unit
def test_the_heading_names_the_game_type() -> None:
    parsed = parse_box_score_page(_bubble_playoff())

    assert parsed.game_type == GAME_TYPE_PLAYOFFS
    assert parsed.game_label == "2020 NBA Western Conference First Round Game 1"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("heading", "game_type"),
    [
        # Headings copied verbatim from pilot pages.
        (
            "Los Angeles Lakers at Denver Nuggets Box Score, October 24, 2023",
            GAME_TYPE_REGULAR_SEASON,
        ),
        (
            "San Antonio Spurs vs Indiana Pacers Box Score, January 23, 2025",
            GAME_TYPE_REGULAR_SEASON,
        ),
        (
            "Play-In Game: Charlotte Hornets at Indiana Pacers Box Score, May 18, 2021",
            GAME_TYPE_PLAY_IN,
        ),
        (
            "2025 NBA Eastern Conference First Round Game 1: Milwaukee Bucks at Indiana Pacers "
            "Box Score, April 19, 2025",
            GAME_TYPE_PLAYOFFS,
        ),
        (
            "In-Season Tournament Final: Indiana Pacers vs Los Angeles Lakers Box Score, "
            "December 9, 2023",
            GAME_TYPE_CUP_FINAL,
        ),
        (
            "NBA Cup Final: Milwaukee Bucks vs Oklahoma City Thunder Box Score, December 17, 2024",
            GAME_TYPE_CUP_FINAL,
        ),
    ],
)
def test_real_headings_classify_every_pilot_game_type(heading: str, game_type: str) -> None:
    parsed = parse_box_score_page(f"<html><body><h1>{heading}</h1></body></html>")

    assert parsed.game_type == game_type


@pytest.mark.unit
def test_an_unrecognized_heading_label_is_reported_not_guessed() -> None:
    parsed = parse_box_score_page(
        "<html><body><h1>NBA All-Star Game: East vs West Box Score, February 16, 2025</h1></body></html>"
    )

    assert parsed.game_type == GAME_TYPE_UNKNOWN
    assert "game_type_unrecognized" in {issue.code for issue in parsed.issues}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("meta", "venue"),
    [
        # Scorebox meta lines copied verbatim from pilot pages.
        (("November 5, 1999", "Tokyo Dome, Tokyo, Japan"), "Tokyo Dome, Tokyo, Japan"),
        (
            ("NBA Cup", "8:30 PM, December 17, 2024", "T-Mobile Arena, Las Vegas, Nevada"),
            "T-Mobile Arena, Las Vegas, Nevada",
        ),
        (("7:30 PM, October 21, 2025", "Logos via Sports Logos.net / About logos"), None),
    ],
)
def test_the_venue_is_the_line_after_the_date(meta: tuple[str, ...], venue: str | None) -> None:
    lines = "".join(f"<div>{line}</div>" for line in meta)
    html = f'<html><body><div class="scorebox"><div class="scorebox_meta">{lines}</div></div></body></html>'

    assert parse_box_score_page(html).venue == venue


@pytest.mark.unit
def test_the_commented_line_score_includes_overtime() -> None:
    parsed = parse_box_score_page(_bubble_playoff())
    assert parsed.visitor is not None and parsed.home is not None

    assert parsed.period_labels == ("1", "2", "3", "4", "OT")
    assert parsed.visitor.line_score == (25, 27, 31, 32, 10)
    assert parsed.visitor.line_score_total == 125
    assert parsed.home.line_score == (31, 28, 19, 37, 20)


@pytest.mark.unit
def test_starters_reserves_and_did_not_play_lines_are_distinguished() -> None:
    parsed = parse_box_score_page(_bubble_playoff())
    assert parsed.visitor is not None
    jazz = parsed.visitor.players

    assert [line.player_id for line in jazz if line.starter] == [
        "mitchdo01",
        "inglejo01",
        "goberru01",
        "onealro01",
        "morgaju01",
    ]
    assert [line.participation for line in jazz[-3:]] == [PARTICIPATION_DID_NOT_PLAY] * 3
    did_not_play = jazz[-1]
    assert (did_not_play.player_id, did_not_play.reason) == ("willini01", "Did Not Play")
    assert did_not_play.seconds_played is None
    assert dict(did_not_play.stats) == {}


@pytest.mark.unit
def test_a_played_line_with_zero_points_is_not_a_did_not_play() -> None:
    parsed = parse_box_score_page(_bubble_playoff())
    assert parsed.visitor is not None
    bradley = next(line for line in parsed.visitor.players if line.player_id == "bradlto01")

    assert bradley.participation == PARTICIPATION_PLAYED
    assert bradley.stats["pts"] == 0
    assert bradley.seconds_played == 650


@pytest.mark.unit
def test_played_lines_carry_seconds_counting_stats_and_plus_minus() -> None:
    parsed = parse_box_score_page(_bubble_playoff())
    assert parsed.visitor is not None
    mitchell = parsed.visitor.players[0]

    assert mitchell.name == "Donovan Mitchell"
    assert mitchell.seconds_played == 2594
    assert mitchell.stats["pts"] == 57
    assert mitchell.plus_minus == -11


@pytest.mark.unit
def test_player_lines_sum_to_team_totals_except_team_turnovers() -> None:
    parsed = parse_box_score_page(_bubble_playoff())

    for team in parsed.teams:
        assert team.totals_seconds == 265 * 60
        for stat in COUNTING_STATS:
            summed = sum(line.stats[stat] or 0 for line in team.played_lines)
            if stat == "tov":
                assert summed <= team.totals[stat]
            else:
                assert summed == team.totals[stat], (team.code, stat)
    assert parsed.visitor is not None
    assert (
        parsed.visitor.totals["tov"]
        - sum(line.stats["tov"] or 0 for line in parsed.visitor.played_lines)
        == 1
    )


@pytest.mark.unit
def test_inactive_players_are_read_per_team() -> None:
    parsed = parse_box_score_page(_bubble_playoff())
    assert parsed.visitor is not None and parsed.home is not None

    assert parsed.visitor.inactive_player_ids == ("conlemi01", "davised01")
    assert parsed.home.inactive_player_ids == ("bartowi01", "cancavl01", "cookty01", "harriga01")


@pytest.mark.unit
def test_a_1999_page_abroad_parses_with_attendance_and_no_overtime() -> None:
    parsed = parse_box_score_page(_page("box_score_199911050SAC_trimmed.html"))
    assert parsed.visitor is not None and parsed.home is not None

    assert parsed.issues == ()
    assert parsed.game_type == GAME_TYPE_REGULAR_SEASON
    assert parsed.venue == "Tokyo Dome, Tokyo, Japan"
    assert parsed.attendance == 32623
    assert parsed.period_labels == ("1", "2", "3", "4")
    assert (parsed.visitor.code, parsed.visitor.scorebox_points) == ("MIN", 95)
    assert (parsed.home.code, parsed.home.scorebox_points) == ("SAC", 100)
    assert parsed.visitor.players[0].player_id == "garneke01"
    assert parsed.home.inactive_player_ids == ()


@pytest.mark.unit
def test_a_page_without_a_scorebox_reports_it() -> None:
    parsed = parse_box_score_page("<html><body></body></html>")

    assert parsed.visitor is None and parsed.home is None
    assert {issue.code for issue in parsed.issues} == {
        "heading_missing",
        "scorebox_teams_unreadable",
    }


@pytest.mark.unit
def test_a_missing_team_box_is_reported() -> None:
    html = _bubble_playoff().replace('id="box-DEN-game-basic"', 'id="box-DEN-q1-basic"')

    parsed = parse_box_score_page(html)

    assert [issue.code for issue in parsed.issues] == ["basic_box_missing"]
    assert parsed.home is not None and parsed.home.players == ()
