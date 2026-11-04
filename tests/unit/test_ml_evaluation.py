"""The Stage 3 protocol on synthetic seasons: metrics, selection, and the one look at the test."""

from __future__ import annotations

import json
import random
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sklearn.metrics import log_loss as sklearn_log_loss

from nba_data.ml import evaluation
from nba_data.ml.artifact import load_artifact
from nba_data.ml.evaluation import (
    EvaluationPlan,
    apply_sigmoid,
    block_bootstrap_interval,
    calibration_bins,
    fit_sigmoid,
    log_losses,
    report_text,
    run_and_publish,
    run_evaluation,
    score_predictions,
    select_model,
    week_blocks,
)
from nba_data.ml.inventory import SeasonInventory
from nba_data.ml.models import (
    MODEL_BOOSTING,
    MODEL_ELO,
    MODEL_HOME_RATE,
    MODEL_LOGISTIC,
    ModelSpec,
)
from nba_data.ml.splits import (
    FIRST_HISTORY_SEASON,
    FIRST_TRAINING_SEASON,
    SELECTION_SEASON,
    TEST_SEASON,
    VALIDATION_SEASONS,
    WINDOWS,
)
from nba_data.ml.team_features import FEATURE_NAMES
from nba_data.ml.team_games import TeamBox, TeamGameRecord

SEASONS = range(FIRST_HISTORY_SEASON, TEST_SEASON + 1)
STRENGTH = {"AAA": 9, "BBB": 5, "CCC": 2, "DDD": -2, "EEE": -5, "FFF": -9}
TEAMS = tuple(STRENGTH)
GAMES_PER_SEASON = 360
CUP_SEASON = 2024
INVENTORY = {
    season: SeasonInventory(GAMES_PER_SEASON, cup_finals=int(season >= CUP_SEASON))
    for season in SEASONS
}
SMALL_PLAN = EvaluationPlan(
    inventory=INVENTORY,
    specs=(
        ModelSpec(MODEL_HOME_RATE),
        ModelSpec(MODEL_ELO, {"k": 20, "home_advantage": 100}),
        ModelSpec(MODEL_LOGISTIC, {"c": 1}),
        ModelSpec(MODEL_BOOSTING, {"learning_rate": 0.1, "max_depth": 3}),
    ),
    resamples=50,
)


def _box(code: str, pts: int | None, noise: int) -> TeamBox:
    return TeamBox(code, pts, 14400, 38 + noise, 85, 12, 16, 20, 9 + noise, 33, 13 - noise)


def _league() -> list[TeamGameRecord]:
    """Twelve short seasons of games between teams of fixed, unequal strength."""

    rng = random.Random(7)
    games = []
    for season in SEASONS:
        for offset in range(120):
            day = date(season - 1, 11, 1) + timedelta(days=offset)
            for slot in range(3):
                home, away = rng.sample(TEAMS, 2)
                margin = STRENGTH[home] - STRENGTH[away] + 3 + rng.randint(-12, 12)
                margin = margin or 1
                games.append(
                    TeamGameRecord(
                        game_id=f"{day:%Y%m%d}{slot}{home}",
                        season_year=season,
                        game_date=day,
                        game_type="regular_season",
                        status="final",
                        neutral_site=False,
                        home=_box(home, 100 + margin, rng.randint(0, 3)),
                        away=_box(away, 100, rng.randint(0, 3)),
                    )
                )
        if season >= CUP_SEASON:
            day = date(season, 3, 15)
            games.append(
                TeamGameRecord(
                    game_id=f"{day:%Y%m%d}0CUP",
                    season_year=season,
                    game_date=day,
                    game_type="cup_final",
                    status="final",
                    neutral_site=True,
                    home=_box("AAA", 110, 1),
                    away=_box("BBB", 100, 1),
                )
            )
    return games


@pytest.fixture(scope="module")
def league() -> list[TeamGameRecord]:
    return _league()


def _reader(games: list[TeamGameRecord], reads: list[int] | None = None) -> Any:
    def read(through_season: int) -> list[TeamGameRecord]:
        if reads is not None:
            reads.append(through_season)
        return [game for game in games if game.season_year <= through_season]

    return read


@pytest.fixture(scope="module")
def result(league: list[TeamGameRecord]) -> evaluation.EvaluationResult:
    return run_evaluation(_reader(league), SMALL_PLAN)


def _dates(weeks: int, per_week: int = 3) -> list[date]:
    start = date(2024, 1, 1)
    return [start + timedelta(weeks=week) for week in range(weeks) for _ in range(per_week)]


def test_log_loss_matches_scikit_learn() -> None:
    labels = np.array([1, 0, 1, 1])
    probabilities = np.array([0.9, 0.2, 0.4, 0.7])

    assert log_losses(labels, probabilities).mean() == pytest.approx(
        sklearn_log_loss(labels, probabilities)
    )


def test_a_certain_wrong_prediction_has_a_finite_loss() -> None:
    assert np.isfinite(log_losses(np.array([1, 0]), np.array([0.0, 1.0]))).all()


def test_week_blocks_group_a_calendar_week_across_a_new_year() -> None:
    blocks = week_blocks([date(2024, 12, 30), date(2025, 1, 2), date(2025, 1, 6)])

    assert blocks[0] == blocks[1] != blocks[2]


def test_the_block_bootstrap_resamples_whole_weeks_reproducibly() -> None:
    values = np.array([0.0] * 5 + [1.0] * 5)
    blocks = np.array([1] * 5 + [2] * 5)

    first = block_bootstrap_interval(values, blocks, resamples=500, seed=1)
    second = block_bootstrap_interval(values, blocks, resamples=500, seed=1)

    assert first == second
    # Two blocks can only resample to 0, 0.5, or 1: whole weeks moved together.
    assert first == (0.0, 1.0)


def test_one_block_has_no_interval() -> None:
    with pytest.raises(ValueError, match="two blocks"):
        block_bootstrap_interval(np.zeros(4), np.ones(4), resamples=10, seed=1)


def test_a_score_holds_every_metric_and_its_sample_size() -> None:
    labels = np.array([1, 0] * 6)
    probabilities = np.array([0.8, 0.3] * 6)

    metrics = score_predictions(labels, probabilities, _dates(4), resamples=20, seed=1)

    assert metrics["games"] == 12
    assert metrics["accuracy"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["brier"] == pytest.approx((0.2**2 + 0.3**2) / 2)
    assert set(metrics["intervals_95"]) == {"log_loss", "brier", "accuracy"}


def test_one_outcome_has_no_roc_auc_and_no_games_is_an_error() -> None:
    labels = np.ones(6, dtype=int)

    metrics = score_predictions(labels, np.full(6, 0.6), _dates(2), resamples=10, seed=1)

    assert metrics["roc_auc"] is None
    with pytest.raises(ValueError, match="no games"):
        score_predictions(np.array([]), np.array([]), [], resamples=10, seed=1)


def test_calibration_bins_count_every_game_and_leave_an_empty_bin_blank() -> None:
    labels = np.array([0, 1, 1, 1])
    probabilities = np.array([0.05, 0.55, 0.58, 1.0])

    bins = calibration_bins(labels, probabilities)

    assert sum(entry["games"] for entry in bins) == 4
    assert bins[5]["games"] == 2
    assert bins[5]["observed_home_win_rate"] == 1.0
    assert bins[9]["games"] == 1
    assert bins[3]["games"] == 0
    assert bins[3]["mean_predicted"] is None


def test_selection_keeps_the_simpler_model_on_an_indistinguishable_pair() -> None:
    rng = np.random.default_rng(1)
    simple = rng.normal(0.65, 0.1, 150)
    complex_ = simple + rng.normal(0.0, 0.05, 150)

    selection = select_model(
        {MODEL_HOME_RATE: simple, MODEL_LOGISTIC: complex_}, _dates(30, 5), resamples=500, seed=1
    )

    assert selection.model == MODEL_HOME_RATE
    assert not selection.steps[0].replaced
    assert selection.steps[0].interval_95[0] < 0 < selection.steps[0].interval_95[1]


def test_selection_takes_the_complex_model_on_a_clear_gain() -> None:
    rng = np.random.default_rng(1)
    simple = rng.normal(0.68, 0.05, 150)

    selection = select_model(
        {MODEL_HOME_RATE: simple, MODEL_ELO: simple - 0.05}, _dates(30, 5), resamples=500, seed=1
    )

    assert selection.model == MODEL_ELO
    assert selection.steps[0].interval_95[1] < 0


def test_selection_walks_in_simplicity_order_whatever_order_it_is_given() -> None:
    base = np.full(150, 0.7)
    jitter = np.random.default_rng(1).normal(0, 0.001, 150)
    losses = {
        MODEL_BOOSTING: base - 0.02 + jitter,
        MODEL_LOGISTIC: base - 0.02 + jitter / 2,
        MODEL_ELO: base - 0.02,
        MODEL_HOME_RATE: base,
    }

    selection = select_model(losses, _dates(30, 5), resamples=200, seed=1)

    assert [step.challenger for step in selection.steps] == [
        MODEL_ELO,
        MODEL_LOGISTIC,
        MODEL_BOOSTING,
    ]
    # Elo clears the baseline; the others are compared to Elo and add nothing.
    assert selection.model == MODEL_ELO
    assert selection.steps[1].incumbent == MODEL_ELO


def test_selecting_from_nothing_fails() -> None:
    with pytest.raises(ValueError, match="no model"):
        select_model({}, [], resamples=10, seed=1)


def test_a_sigmoid_recovers_an_overconfident_forecast() -> None:
    rng = np.random.default_rng(3)
    honest = rng.uniform(0.2, 0.8, 4000)
    labels = (rng.uniform(size=4000) < honest).astype(int)
    overconfident = apply_sigmoid(honest, 3.0, 0.0)

    slope, intercept = fit_sigmoid(labels, overconfident)

    assert slope == pytest.approx(1 / 3, abs=0.05)
    assert abs(intercept) < 0.1


def test_the_protocol_reports_every_model_window_fold_and_split(
    result: evaluation.EvaluationResult,
) -> None:
    report = result.report

    assert len(report["validation"]) == len(SMALL_PLAN.specs) * len(WINDOWS)
    for entry in report["validation"]:
        assert set(entry["folds"]) == {str(season) for season in VALIDATION_SEASONS}
    assert {(entry["model"], entry["window"]) for entry in report["selection_season"]} == {
        (spec.model, window.name) for spec in SMALL_PLAN.specs for window in WINDOWS
    }
    assert all(len(entry["calibration_bins"]) == 10 for entry in report["selection_season"])
    for entry in report["validation"]:
        for fold in entry["folds"].values():
            assert sum(item["games"] for item in fold["calibration_bins"]) == fold["games"]
    assert report["feature_definition_version"] == "team-pregame-v1"
    ids = report["dataset"]["game_ids_by_season"]
    assert set(ids) == {str(season) for season in range(FIRST_TRAINING_SEASON, TEST_SEASON + 1)}
    flattened = [game_id for season_ids in ids.values() for game_id in season_ids]
    assert len(flattened) == len(set(flattened)) == GAMES_PER_SEASON * 11


def test_every_model_is_scored_on_the_same_games(result: evaluation.EvaluationResult) -> None:
    ids = result.report["dataset"]["game_ids_by_season"]

    for entry in result.report["validation"]:
        for season, fold in entry["folds"].items():
            assert fold["games"] == len(ids[season])
    for entry in result.report["selection_season"]:
        assert entry["metrics"]["games"] == len(ids[str(SELECTION_SEASON)])


def test_each_model_is_finalised_on_its_lowest_mean_validation_loss(
    result: evaluation.EvaluationResult,
) -> None:
    report = result.report
    for model, finalist in report["selection"]["finalists"].items():
        losses = [e["mean_log_loss"] for e in report["validation"] if e["model"] == model]
        assert finalist["mean_validation_log_loss"] == min(losses)


def test_a_known_good_signal_beats_the_baseline_and_goes_ahead(
    result: evaluation.EvaluationResult,
) -> None:
    report = result.report

    assert report["selection"]["selected"] != MODEL_HOME_RATE
    assert report["test"]["stage_5_go"] is True
    assert (
        report["test"]["selected"]["metrics"]["log_loss"]
        < report["test"]["home_rate_baseline"]["metrics"]["log_loss"]
    )
    assert result.model.name == report["selection"]["selected"]
    assert report["calibration"]["fitted_on_season"] == 2024


def test_home_rate_selected_cannot_beat_itself_so_stage_5_stays_blocked(
    league: list[TeamGameRecord],
) -> None:
    plan = EvaluationPlan(specs=(ModelSpec(MODEL_HOME_RATE),), resamples=20, inventory=INVENTORY)

    result = run_evaluation(_reader(league), plan)

    assert result.report["selection"]["selected"] == MODEL_HOME_RATE
    if not result.report["calibration"]["kept"]:
        assert result.report["test"]["stage_5_go"] is False


def test_the_test_season_is_read_only_after_selection(
    league: list[TeamGameRecord], monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_select = evaluation.select_model

    def spy_select(*args: Any, **kwargs: Any) -> evaluation.Selection:
        events.append("select")
        return real_select(*args, **kwargs)

    def read(through_season: int) -> list[TeamGameRecord]:
        events.append(f"read {through_season}")
        return [game for game in league if game.season_year <= through_season]

    monkeypatch.setattr(evaluation, "select_model", spy_select)

    run_evaluation(read, SMALL_PLAN)

    assert events == [f"read {SELECTION_SEASON}", "select", f"read {TEST_SEASON}"]


def test_changing_the_test_season_changes_nothing_before_the_test(
    league: list[TeamGameRecord], result: evaluation.EvaluationResult
) -> None:
    flipped = [
        replace(game, home=game.away, away=game.home) if game.season_year == TEST_SEASON else game
        for game in league
    ]

    changed = run_evaluation(_reader(flipped), SMALL_PLAN).report

    for section in ("validation", "selection_season", "selection", "calibration"):
        assert changed[section] == result.report[section]
    assert changed["test"] != result.report["test"]


def test_no_fit_sees_its_target_season_or_a_later_one(
    league: list[TeamGameRecord], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[set[int], int]] = []
    real_fit = evaluation._fit

    def spy_fit(spec: ModelSpec, window: Any, target: int, data: Any) -> Any:
        real_build = evaluation.build_model

        def spying_build(inner: ModelSpec) -> Any:
            model = real_build(inner)
            real_model_fit = model.fit

            def fit(training: Any) -> Any:
                seasons = {row.season_year for row in training.rows}
                seasons |= {game.season_year for game in training.history}
                seen.append((seasons, target))
                return real_model_fit(training)

            model.fit = fit  # type: ignore[method-assign]
            return model

        monkeypatch.setattr(evaluation, "build_model", spying_build)
        try:
            return real_fit(spec, window, target, data)
        finally:
            monkeypatch.setattr(evaluation, "build_model", real_build)

    monkeypatch.setattr(evaluation, "_fit", spy_fit)

    run_evaluation(_reader(league), SMALL_PLAN)

    assert seen
    assert all(max(seasons) < target for seasons, target in seen)


def test_an_unscored_target_is_a_missing_game(league: list[TeamGameRecord]) -> None:
    victim = next(game for game in league if game.season_year == 2022)
    blanked = [
        replace(game, home=replace(game.home, pts=None)) if game is victim else game
        for game in league
    ]

    with pytest.raises(ValueError, match="season 2022: 359 scored regular-season games"):
        run_evaluation(_reader(blanked), SMALL_PLAN)


@pytest.mark.parametrize("absent", [FIRST_HISTORY_SEASON, 2021, SELECTION_SEASON, TEST_SEASON])
def test_a_missing_season_fails_instead_of_passing_empty(
    league: list[TeamGameRecord], absent: int
) -> None:
    games = [game for game in league if game.season_year != absent]

    with pytest.raises(ValueError, match=f"season {absent}: 0 scored regular-season games"):
        run_evaluation(_reader(games), SMALL_PLAN)


def test_a_partial_test_season_stops_after_selection_with_no_result(
    league: list[TeamGameRecord],
) -> None:
    kept = [
        game
        for index, game in enumerate(league)
        if game.season_year != TEST_SEASON or index % 4 == 0
    ]

    with pytest.raises(ValueError, match=f"season {TEST_SEASON}: \\d+ scored regular-season"):
        run_evaluation(_reader(kept), SMALL_PLAN)


def test_a_documented_quarantine_is_allowed_and_reported(league: list[TeamGameRecord]) -> None:
    victim = next(game for game in league if game.season_year == 2022)
    games = [game for game in league if game is not victim]
    inventory = {
        **INVENTORY,
        2022: SeasonInventory(GAMES_PER_SEASON, quarantined=(victim.game_id,)),
    }

    report = run_evaluation(_reader(games), replace(SMALL_PLAN, inventory=inventory)).report

    assert report["dataset"]["skipped_target_game_ids"] == [victim.game_id]
    assert victim.game_id not in report["dataset"]["game_ids_by_season"]["2022"]


def test_a_changed_history_between_selection_and_the_test_is_refused(
    league: list[TeamGameRecord],
) -> None:
    def read(through_season: int) -> list[TeamGameRecord]:
        games = [game for game in league if game.season_year <= through_season]
        if through_season == TEST_SEASON:
            return [
                replace(game, neutral_site=True) if game is games[0] else game for game in games
            ]
        return games

    with pytest.raises(ValueError, match="changed between selection and the test"):
        run_evaluation(read, SMALL_PLAN)


def test_the_report_names_history_only_games_and_fingerprints_the_input(
    league: list[TeamGameRecord], result: evaluation.EvaluationResult
) -> None:
    dataset = result.report["dataset"]
    history_only = dataset["history_only_game_ids_by_season"]

    assert len(history_only["2015"]) == GAMES_PER_SEASON
    assert history_only[str(CUP_SEASON)] == [
        game.game_id
        for game in league
        if game.season_year == CUP_SEASON and game.game_type == "cup_final"
    ]
    changed = [replace(league[0], neutral_site=True), *league[1:]]
    other = run_evaluation(_reader(changed), SMALL_PLAN).report["dataset"]
    assert len(dataset["input_sha256"]) == 64
    assert other["input_sha256"] != dataset["input_sha256"]


def test_a_reader_that_returns_a_later_season_is_refused(league: list[TeamGameRecord]) -> None:
    with pytest.raises(ValueError, match="after 2025"):
        run_evaluation(lambda _: league, SMALL_PLAN)


def test_rerunning_gives_a_byte_identical_report_and_the_same_artifact(
    league: list[TeamGameRecord], tmp_path: Path
) -> None:
    first = run_and_publish(
        _reader(league), output=tmp_path / "one.json", artifact_dir=tmp_path / "m", plan=SMALL_PLAN
    )
    second = run_and_publish(
        _reader(league), output=tmp_path / "two.json", artifact_dir=tmp_path / "m", plan=SMALL_PLAN
    )

    assert (tmp_path / "one.json").read_bytes() == (tmp_path / "two.json").read_bytes()
    assert first["artifact"] == second["artifact"]
    assert [path.name for path in (tmp_path / "m").iterdir()] == [first["artifact"]]


def test_the_published_report_and_metadata_name_the_same_model(
    league: list[TeamGameRecord], tmp_path: Path
) -> None:
    output = tmp_path / "report.json"
    summary = run_and_publish(
        _reader(league), output=output, artifact_dir=tmp_path / "m", plan=SMALL_PLAN
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    model, metadata = load_artifact(tmp_path / "m" / summary["artifact"])

    assert report["artifact"]["directory"] == summary["artifact"]
    assert metadata["model"] == report["selection"]["selected"] == model.name
    assert metadata["training_seasons"][-1] == TEST_SEASON
    assert metadata["feature_definition_version"] == "team-pregame-v1"
    assert metadata["feature_names"] == list(FEATURE_NAMES)
    assert metadata["seed"] == 20261018
    assert summary["artifact"].endswith(metadata["model_sha256"][:12])


def test_the_report_text_is_strict_json(result: evaluation.EvaluationResult) -> None:
    artifact = evaluation.SavedArtifact(Path("x"), "a" * 64)

    assert json.loads(report_text(result.report, artifact))["artifact"]["sha12"] == "a" * 12
