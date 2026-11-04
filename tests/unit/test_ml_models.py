"""The four candidates: one interface, valid probabilities, no peeking past the cutoff."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from nba_data.ml.elo import EloRatings, expected_home_win
from nba_data.ml.models import (
    DEFAULT_SPECS,
    MODEL_BOOSTING,
    MODEL_ELO,
    MODEL_HOME_RATE,
    MODEL_LOGISTIC,
    CalibratedModel,
    EloModel,
    HomeRateModel,
    ModelSpec,
    SklearnModel,
    TrainingSet,
    build_model,
)
from nba_data.ml.team_features import FEATURE_NAMES, TeamFeatureRow, build_team_features
from nba_data.ml.team_games import TeamBox, TeamGameRecord

START = date(2024, 1, 1)


def _box(code: str, pts: int | None) -> TeamBox:
    return TeamBox(code, pts, 14400, 40, 85, 12, 18, 22, 10, 33, 13)


def _game(day: date, home: str, away: str, home_pts: int | None, away_pts: int | None,
          neutral: bool | None = False) -> TeamGameRecord:  # fmt: skip
    return TeamGameRecord(
        f"{day:%Y%m%d}0{home}", 2024, day, "regular_season", "final", neutral,
        _box(home, home_pts), _box(away, away_pts),
    )  # fmt: skip


def _league(games: int = 60) -> list[TeamGameRecord]:
    teams = ("AAA", "BBB", "CCC", "DDD")
    return [
        _game(
            START + timedelta(days=offset),
            teams[offset % 4],
            teams[(offset + 1) % 4],
            100 + (offset * 7) % 19,
            100 + (offset * 11) % 17 + (1 if (offset * 7) % 19 == (offset * 11) % 17 else 0),
        )
        for offset in range(games)
    ]


def _training(games: list[TeamGameRecord]) -> TrainingSet:
    build = build_team_features(games, target_ids=[game.game_id for game in games])
    by_id = {game.game_id: game for game in games}
    labels = [
        int((by_id[row.game_id].home.pts or 0) > (by_id[row.game_id].away.pts or 0))
        for row in build.rows
    ]
    return TrainingSet(rows=build.rows, labels=labels, history=games)


def _row(game: TeamGameRecord, is_neutral: bool = False) -> TeamFeatureRow:
    values = dict.fromkeys(FEATURE_NAMES)
    values["is_neutral"] = is_neutral
    return TeamFeatureRow(
        game_id=game.game_id,
        game_date=game.game_date,
        season_year=game.season_year,
        home_team=game.home.team_code,
        away_team=game.away.team_code,
        values=values,
    )


SPECS = (
    ModelSpec(MODEL_HOME_RATE),
    ModelSpec(MODEL_ELO, {"k": 20, "home_advantage": 100}),
    ModelSpec(MODEL_LOGISTIC, {"c": 1}),
    ModelSpec(MODEL_BOOSTING, {"learning_rate": 0.1, "max_depth": 3}),
)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.model)
def test_every_model_gives_one_valid_probability_per_row(spec: ModelSpec) -> None:
    training = _training(_league())
    model = build_model(spec).fit(training)

    probabilities = model.predict_proba(training.rows)

    assert model.name == spec.model
    assert len(probabilities) == len(training.rows)
    assert all(isinstance(value, float) and 0.0 <= value <= 1.0 for value in probabilities)


@pytest.mark.parametrize("spec", SPECS[2:], ids=lambda spec: spec.model)
def test_the_estimator_s_home_and_away_probabilities_sum_to_one_and_home_is_returned(
    spec: ModelSpec,
) -> None:
    training = _training(_league())
    model = build_model(spec).fit(training)
    assert isinstance(model, SklearnModel)
    matrix = np.array(
        [[row.values[name] for name in FEATURE_NAMES] for row in training.rows], dtype=float
    )

    both = model.estimator.predict_proba(matrix)

    assert both.sum(axis=1) == pytest.approx(1.0)
    assert list(model.estimator.classes_) == [0, 1]
    assert model.predict_proba(training.rows) == pytest.approx(both[:, 1].tolist())


def test_the_grid_is_the_one_fixed_on_the_card() -> None:
    by_model: dict[str, list[dict[str, object]]] = {}
    for spec in DEFAULT_SPECS:
        by_model.setdefault(spec.model, []).append(spec.configuration)

    assert by_model[MODEL_HOME_RATE] == [{}]
    assert len(by_model[MODEL_ELO]) == 6
    assert {config["k"] for config in by_model[MODEL_ELO]} == {15, 20, 25}
    assert {config["home_advantage"] for config in by_model[MODEL_ELO]} == {70, 100}
    assert [config["c"] for config in by_model[MODEL_LOGISTIC]] == [0.01, 0.1, 1, 10]
    assert len(by_model[MODEL_BOOSTING]) == 4
    assert {config["learning_rate"] for config in by_model[MODEL_BOOSTING]} == {0.05, 0.1}
    assert {config["max_depth"] for config in by_model[MODEL_BOOSTING]} == {3, None}


def test_the_home_rate_ignores_neutral_training_games_and_flips_a_coin_on_them() -> None:
    games = _league(4)
    rows = [_row(games[0]), _row(games[1]), _row(games[2]), _row(games[3], is_neutral=True)]
    model = HomeRateModel().fit(TrainingSet(rows=rows, labels=[1, 1, 0, 0], history=[]))

    assert model.home_rate == pytest.approx(2 / 3)
    assert model.predict_proba(rows[-2:]) == pytest.approx([2 / 3, 0.5])


def test_the_home_rate_needs_a_home_game_and_a_fit() -> None:
    game = _game(START, "AAA", "BBB", 100, 90)
    with pytest.raises(ValueError, match="home floor"):
        HomeRateModel().fit(TrainingSet(rows=[_row(game, True)], labels=[1], history=[]))
    with pytest.raises(ValueError, match="not fitted"):
        HomeRateModel().predict_proba([_row(game)])


def test_elo_reads_only_games_at_or_before_the_results_cutoff() -> None:
    first = _game(START, "AAA", "BBB", 110, 90)
    inside = _game(START + timedelta(days=8), "AAA", "BBB", 120, 90)
    late = _game(START + timedelta(days=9), "AAA", "BBB", 90, 130)
    target = _game(START + timedelta(days=10), "AAA", "BBB", None, None)

    model = EloModel(20, 100).fit(TrainingSet([], [], [first]))
    model.observe([inside, late])
    [probability] = model.predict_proba([_row(target)])

    ratings = EloRatings(20, 100)
    ratings.update(first)
    ratings.update(inside)
    assert probability == pytest.approx(
        expected_home_win(ratings.pregame("AAA", 2024), ratings.pregame("BBB", 2024), 100)
    )
    assert probability != pytest.approx(
        EloModel(20, 100).fit(TrainingSet([], [], [first])).predict_proba([_row(target)])[0]
    )


def test_elo_with_the_feature_constants_matches_the_feature_ratings() -> None:
    games = _league()
    target = games[-1]
    build = build_team_features(games, target_ids=[target.game_id])
    [row] = build.rows

    [probability] = EloModel(20, 100).fit(TrainingSet([], [], games)).predict_proba([row])

    assert probability == pytest.approx(
        expected_home_win(row.values["elo_home"], row.values["elo_away"], 100)  # type: ignore[arg-type]
    )


def test_elo_zeroes_home_advantage_only_on_a_known_neutral_floor() -> None:
    target = _game(START, "AAA", "BBB", None, None)
    model = EloModel(20, 70).fit(TrainingSet([], [], []))

    home, neutral = model.predict_proba([_row(target), _row(target, is_neutral=True)])

    assert neutral == pytest.approx(0.5)
    assert home == pytest.approx(expected_home_win(1500.0, 1500.0, 70))


def test_elo_ignores_a_game_with_a_missing_score_and_a_repeated_observation() -> None:
    played = _game(START, "AAA", "BBB", 110, 90)
    blank = replace(_game(START + timedelta(days=1), "AAA", "BBB", None, 90))
    target = _game(START + timedelta(days=10), "AAA", "BBB", None, None)
    once = EloModel(20, 100).fit(TrainingSet([], [], [played]))
    twice = EloModel(20, 100).fit(TrainingSet([], [], [played]))
    twice.observe([played, blank])

    assert once.predict_proba([_row(target)]) == twice.predict_proba([_row(target)])


def test_sklearn_models_impute_a_feature_blank_in_all_of_training() -> None:
    training = _training(_league())
    blanked = [
        replace(row, values={**row.values, "diff_margin_season": None}) for row in training.rows
    ]
    model = build_model(SPECS[2]).fit(TrainingSet(blanked, training.labels, []))

    assert np.isfinite(model.predict_proba(blanked)).all()


def test_a_calibrated_model_shifts_the_base_probability_through_its_sigmoid() -> None:
    games = _league(4)
    rows = [_row(game) for game in games]
    base = HomeRateModel().fit(TrainingSet(rows, [1, 1, 1, 0], []))

    identity = CalibratedModel(base, slope=1.0, intercept=0.0)
    flat = CalibratedModel(base, slope=0.0, intercept=0.0)

    assert identity.name == MODEL_HOME_RATE
    assert identity.predict_proba(rows) == pytest.approx([0.75] * 4)
    assert flat.predict_proba(rows) == pytest.approx([0.5] * 4)


def test_an_unknown_model_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown model"):
        build_model(ModelSpec("magic"))
