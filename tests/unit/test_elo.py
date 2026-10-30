"""Elo for `team-pregame-v1`: the update, neutral floors, and the season carry-over."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from nba_data.ml.elo import (
    ELO_START,
    EloRatings,
    expected_home_win,
    home_advantage,
    margin_multiplier,
)
from nba_data.ml.team_games import TeamBox, TeamGameRecord


def _game(
    game_id: str,
    home: str,
    away: str,
    home_pts: int,
    away_pts: int,
    *,
    season: int = 2024,
    neutral: bool | None = False,
) -> TeamGameRecord:
    def box(code: str, pts: int) -> TeamBox:
        return TeamBox(code, pts, 14400, 40, 85, 12, 18, 22, 10, 33, 13)

    return TeamGameRecord(
        game_id=game_id,
        season_year=season,
        game_date=date(2024, 1, 1),
        game_type="regular_season",
        status="final",
        neutral_site=neutral,
        home=box(home, home_pts),
        away=box(away, away_pts),
    )


SEQUENCE = (
    _game("g1", "AAA", "BBB", 110, 100),
    _game("g2", "BBB", "CCC", 95, 90, neutral=True),
    _game("g3", "CCC", "AAA", 99, 105),
)


def test_a_hand_computed_three_game_sequence() -> None:
    # g1: 1500 v 1500 with 100 home points. E = 1/(1+10^(-100/400)) = 0.640065;
    #     multiplier = 13^0.8 / (7.5 + 0.006·100) = 0.960881;
    #     shift = 20 · 0.960881 · (1 − 0.640065) = 6.917095.
    # g2: neutral, so no home points. 1493.082905 v 1500: E = 0.490047;
    #     winner diff −6.917095, multiplier = 8^0.8 / (7.5 − 0.041503) = 0.707653;
    #     shift = 20 · 0.707653 · 0.509953 = 7.217403.
    # g3: CCC home at 1492.782597 + 100 v AAA 1506.917095: E = 0.621115;
    #     winner (away) diff = 1506.917095 − 1592.782597 = −85.865502,
    #     multiplier = 9^0.8 / (7.5 − 0.515193) = 0.830309;
    #     shift = 20 · 0.830309 · (0 − 0.621115) = −10.314336.
    ratings = EloRatings()
    for game in SEQUENCE:
        ratings.update(game)

    assert ratings.pregame("AAA", 2024) == pytest.approx(1517.2314313025836, abs=1e-9)
    assert ratings.pregame("BBB", 2024) == pytest.approx(1500.3003079250645, abs=1e-9)
    assert ratings.pregame("CCC", 2024) == pytest.approx(1482.4682607723519, abs=1e-9)


def test_ratings_are_zero_sum_within_a_game() -> None:
    ratings = EloRatings()
    for game in SEQUENCE:
        ratings.update(game)

    total = sum(ratings.pregame(code, 2024) for code in ("AAA", "BBB", "CCC"))
    assert total == pytest.approx(3 * ELO_START, abs=1e-9)


def test_a_neutral_floor_zeroes_home_advantage_and_an_undetermined_one_does_not() -> None:
    assert home_advantage(True) == 0.0
    assert home_advantage(False) == 100.0
    assert home_advantage(None) == 100.0

    neutral, home, undetermined = EloRatings(), EloRatings(), EloRatings()
    neutral.update(_game("n", "AAA", "BBB", 110, 100, neutral=True))
    home.update(_game("h", "AAA", "BBB", 110, 100, neutral=False))
    undetermined.update(_game("u", "AAA", "BBB", 110, 100, neutral=None))

    # Even teams on a neutral floor: E = 0.5, multiplier = 13^0.8 / 7.5.
    expected_shift = 20 * (13**0.8 / 7.5) * 0.5
    assert neutral.pregame("AAA", 2024) == pytest.approx(1500 + expected_shift, abs=1e-9)
    assert home.pregame("AAA", 2024) == undetermined.pregame("AAA", 2024)
    assert home.pregame("AAA", 2024) < neutral.pregame("AAA", 2024)


def test_a_rating_regresses_a_quarter_toward_1505_between_seasons() -> None:
    ratings = EloRatings()
    ratings.update(_game("g", "AAA", "BBB", 130, 90, season=2023))
    end_of_season = ratings.pregame("AAA", 2023)

    assert ratings.pregame("AAA", 2024) == pytest.approx(0.75 * end_of_season + 0.25 * 1505)
    # A skipped season regresses once, not twice.
    assert ratings.pregame("AAA", 2026) == ratings.pregame("AAA", 2024)


def test_the_carry_over_feeds_the_first_game_of_the_new_season() -> None:
    ratings = EloRatings()
    ratings.update(_game("g", "AAA", "BBB", 130, 90, season=2023))
    carried_a = ratings.pregame("AAA", 2024)
    carried_b = ratings.pregame("BBB", 2024)

    ratings.update(_game("h", "AAA", "BBB", 100, 101, season=2024, neutral=True))

    shift = (
        20
        * margin_multiplier(-1, carried_b - carried_a)
        * (0 - expected_home_win(carried_a, carried_b, 0.0))
    )
    assert ratings.pregame("AAA", 2024) == pytest.approx(carried_a + shift, abs=1e-9)


def test_a_new_team_code_starts_at_1500_in_any_season() -> None:
    ratings = EloRatings()
    ratings.update(_game("g", "AAA", "BBB", 110, 100, season=2023))

    assert ratings.pregame("NEW", 2023) == ELO_START
    assert ratings.pregame("NEW", 2030) == ELO_START


def test_replaying_the_same_games_gives_identical_ratings() -> None:
    first, second = EloRatings(), EloRatings()
    for ratings in (first, second):
        for game in SEQUENCE:
            ratings.update(game)

    for code in ("AAA", "BBB", "CCC"):
        assert first.pregame(code, 2024) == second.pregame(code, 2024)


@pytest.mark.parametrize(
    ("home_pts", "away_pts", "message"),
    [(None, 100, "both final scores"), (100, 100, "cannot be tied")],
)
def test_an_unscored_or_tied_game_is_refused(
    home_pts: int | None, away_pts: int, message: str
) -> None:
    game = _game("bad", "AAA", "BBB", 0, away_pts)
    game = replace(game, home=replace(game.home, pts=home_pts))

    with pytest.raises(ValueError, match=message):
        EloRatings().update(game)
