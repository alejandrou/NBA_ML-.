"""The pure decisions behind `ml predict`: cutoff, rounding, favorite, and reasons."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from nba_data.ml.predict import (
    Fixture,
    PredictionError,
    WindowGame,
    build_prediction_rows,
    cutoff_for,
    games_past_the_regular_season,
    latest_complete_date,
    resolve_neutral_sites,
    round_probabilities,
    withheld_games,
)
from nba_data.ml.team_features import TeamFeatureRow
from nba_data.ml.team_games import TeamBox, TeamGameRecord

D = date(2026, 12, 1)


def _box(code: str, pts: int | None = 100) -> TeamBox:
    return TeamBox(code, pts, 14_400, 40, 85, 12, 15, 20, 10, 32, 13)


def _final(day: int, home: str = "AAA", away: str = "BBB") -> TeamGameRecord:
    played = D + timedelta(days=day)
    return TeamGameRecord(
        f"{played:%Y%m%d}0{home}", 2027, played, "regular_season", "final", False,
        _box(home, 110), _box(away, 100),
    )


def _scheduled(day: int, home: str = "AAA", away: str = "BBB") -> TeamGameRecord:
    played = D + timedelta(days=day)
    return TeamGameRecord(
        f"{played:%Y%m%d}0{home}", 2027, played, None, "scheduled", None,
        _box(home, None), _box(away, None),
    )


def _window(game: TeamGameRecord, row_id: int = 1) -> WindowGame:
    return WindowGame(row_id, game.game_id, game.game_date, game.status, game.game_type)


class _Fixed:
    name = "fixed"

    def __init__(self, probability: float = 0.6) -> None:
        self.probability = probability
        self.observed: list[TeamGameRecord] = []
        self.rows: list[TeamFeatureRow] = []

    def fit(self, training: object) -> _Fixed:
        return self

    def observe(self, games: Iterable[TeamGameRecord]) -> None:
        self.observed.extend(games)

    def predict_proba(self, rows: Sequence[TeamFeatureRow]) -> list[float]:
        self.rows.extend(rows)
        return [self.probability] * len(rows)


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        ([(D, "final"), (D + timedelta(days=1), "final")], D + timedelta(days=1)),
        ([(D, "final"), (D + timedelta(days=1), "scheduled")], D),
        # A date is not complete while a game on it is still open.
        ([(D, "final"), (D, "scheduled")], None),
        # A later final does not move the cutoff past a game left behind.
        (
            [
                (D, "final"),
                (D + timedelta(days=1), "scheduled"),
                (D + timedelta(days=2), "final"),
            ],
            D,
        ),
        ([], None),
    ],
)
def test_the_latest_complete_date(
    schedule: list[tuple[date, str]], expected: date | None
) -> None:
    assert latest_complete_date(schedule) == expected


def test_the_cutoff_is_the_earlier_of_the_two_bounds() -> None:
    assert cutoff_for(D, D) == D - timedelta(days=2)
    assert cutoff_for(D, D - timedelta(days=9)) == D - timedelta(days=9)


@pytest.mark.parametrize(
    ("probability", "home", "away", "favorite"),
    [
        # Exact binary ties: 1/128 and 3/128 end in a 5 at the seventh place.
        (0.0078125, "0.007812", "0.992188", "away"),
        (0.0234375, "0.023438", "0.976562", "away"),
        (0.5, "0.500000", "0.500000", None),
        (0.5000001, "0.500000", "0.500000", None),
        (0.75, "0.750000", "0.250000", "home"),
        (1.0, "1.000000", "0.000000", "home"),
        (0.0, "0.000000", "1.000000", "away"),
    ],
)
def test_rounding_keeps_the_sum_exact(
    probability: float, home: str, away: str, favorite: str | None
) -> None:
    rounded_home, rounded_away, rounded_favorite = round_probabilities(probability)

    assert (str(rounded_home), str(rounded_away), rounded_favorite) == (home, away, favorite)
    assert rounded_home + rounded_away == Decimal(1)


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.01, 1.01])
def test_an_invalid_probability_stops_the_run(probability: float) -> None:
    with pytest.raises(PredictionError):
        round_probabilities(probability)


def test_four_prior_games_are_not_enough_and_five_are() -> None:
    history = [_final(day) for day in range(5)]
    target = _scheduled(20)
    latest = D + timedelta(days=4)

    enough = build_prediction_rows(_Fixed(), [*history, target], [_window(target)], latest, 7)
    short = build_prediction_rows(
        _Fixed(), [*history[:4], target], [_window(target)], latest - timedelta(days=1), 7
    )

    assert enough[0]["status"] == "available"
    assert short[0]["unavailable_reason"] == "insufficient_history"
    assert short[0]["home_win_probability"] is None


@pytest.mark.parametrize("status", ["final", "postponed"])
def test_a_game_not_scheduled_never_reaches_the_model(status: str) -> None:
    model = _Fixed()
    game = WindowGame(1, "202612010AAA", D, status, "regular_season" if status == "final" else None)

    [row] = build_prediction_rows(model, [], [game], D, 7)

    assert row["unavailable_reason"] == "game_not_scheduled"
    assert row["inputs"] == {}
    assert model.rows == []


def test_the_model_observes_nothing_past_the_cutoff() -> None:
    history = [_final(day) for day in range(5)]
    late = _final(6, "CCC", "DDD")
    target = _scheduled(20)
    model = _Fixed()

    build_prediction_rows(model, [*history, late, target], [_window(target)], D + timedelta(days=4), 7)

    assert late not in model.observed
    assert set(model.observed) == set(history)


def test_a_skipped_game_gets_no_row() -> None:
    game = _scheduled(20)

    assert build_prediction_rows(_Fixed(), [game], [_window(game)], D, 7, {game.game_id}) == []


@pytest.mark.parametrize("status", ["final", "postponed"])
def test_a_game_already_issued_keeps_its_rows_and_gets_no_other(status: str) -> None:
    game = WindowGame(1, "202612010AAA", D, status, "regular_season" if status == "final" else None)

    assert build_prediction_rows(_Fixed(), [], [game], D, 7, already_issued={game.game_id}) == []


def test_blank_statistics_in_the_last_five_games_refuse_the_forecast() -> None:
    blank = TeamBox("AAA", None, None, None, None, None, None, None, None, None, None)
    history = [_final(day) for day in range(4)]
    last = replace(_final(4), home=blank)
    target = _scheduled(20)
    model = _Fixed()

    [row] = build_prediction_rows(
        model, [*history, last, target], [_window(target)], D + timedelta(days=4), 7
    )

    assert row["unavailable_reason"] == "insufficient_history"
    assert row["inputs"]["games_in_season_before_home"] == 5
    assert row["inputs"]["complete_recent_games_home"] == 4
    assert model.rows == []


def test_a_blank_game_older_than_the_last_five_does_not_block() -> None:
    old = replace(_final(0), away=TeamBox("BBB", None, *[None] * 9))
    history = [old, *(_final(day) for day in range(1, 6))]
    target = _scheduled(20)

    [row] = build_prediction_rows(
        _Fixed(), [*history, target], [_window(target)], D + timedelta(days=5), 7
    )

    assert row["status"] == "available"
    assert row["inputs"]["complete_recent_games_away"] == 5


def _fixture(
    game_id: str,
    venue: str | None = "Home Arena",
    *,
    day: int = 0,
    neutral: bool | None = None,
    home: str = "AAA",
    away: str = "BBB",
    status: str = "scheduled",
    game_type: str | None = None,
) -> Fixture:
    return Fixture(
        game_id, 2027, D + timedelta(days=day), status, game_type, neutral, venue, home, away
    )


def _home_games(count: int = 3) -> list[Fixture]:
    return [_fixture(f"home{index}", day=index) for index in range(count)]


def test_a_game_away_from_the_teams_arena_is_neutral() -> None:
    resolved = resolve_neutral_sites([*_home_games(), _fixture("paris", "Accor Arena, Paris")])

    assert resolved["home0"] is False
    assert resolved["paris"] is True


def test_a_box_score_venue_matches_the_schedules_arena() -> None:
    resolved = resolve_neutral_sites([*_home_games(), _fixture("played", "Home Arena, City, ST")])

    assert resolved["played"] is False


def test_a_stored_flag_wins_over_the_arena() -> None:
    resolved = resolve_neutral_sites([*_home_games(), _fixture("x", "Elsewhere", neutral=False)])

    assert resolved["x"] is False


@pytest.mark.parametrize(
    "fixtures",
    [
        [_fixture("x", None), *_home_games()],
        [_fixture("x", "Home Arena"), _fixture("y", "Home Arena")],
        [
            _fixture("x", "One"), _fixture("y", "One"), _fixture("z", "One"),
            _fixture("a", "Two"), _fixture("b", "Two"), _fixture("c", "Two"),
        ],
    ],
    ids=["no arena", "too few home games", "two arenas tied"],
)
def test_an_undeterminable_venue_stays_unknown(fixtures: list[Fixture]) -> None:
    assert resolve_neutral_sites(fixtures)["x"] is None


def test_games_beyond_the_82nd_are_past_the_regular_season() -> None:
    fixtures = [_fixture(f"g{index:03}", day=index) for index in range(83)]

    assert games_past_the_regular_season(fixtures) == {"g082"}


def test_a_played_cup_final_and_a_postponement_do_not_count_toward_the_82() -> None:
    fixtures = [
        _fixture("cup", day=-2, status="final", game_type="cup_final"),
        _fixture("moved", day=-1, status="postponed"),
        *(_fixture(f"g{index:03}", day=index) for index in range(82)),
    ]

    assert games_past_the_regular_season(fixtures) == set()


@pytest.mark.parametrize(
    ("game_type", "neutral", "past", "reason"),
    [
        (None, False, False, None),
        ("regular_season", True, False, None),
        ("playoffs", False, False, "not_regular_season"),
        (None, None, False, "unknown_venue"),
        ("regular_season", None, False, "unknown_venue"),
        (None, True, False, "unconfirmed_competition"),
        (None, False, True, "unconfirmed_competition"),
    ],
)
def test_the_eligibility_policy(
    game_type: str | None, neutral: bool | None, past: bool, reason: str | None
) -> None:
    game = WindowGame(1, "x", D, "scheduled", game_type)

    withheld = withheld_games([game], {"x": neutral}, {"x"} if past else set())

    assert withheld == ({reason: ["x"]} if reason else {})


def test_a_finished_game_is_never_withheld() -> None:
    assert withheld_games([WindowGame(1, "x", D, "final", "playoffs")], {}, {"x"}) == {}
