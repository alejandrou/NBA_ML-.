"""The Stage 3 protocol: rolling validation, selection, calibration, one test.

Every rule here was fixed on F8-007 before any result existed. The test season
is requested from `read_games` only after selection and the calibration check.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from nba_data.ml._numpy import Array, np
from nba_data.ml.artifact import SavedArtifact, publish_text, save_artifact
from nba_data.ml.inventory import GAME_INVENTORY, SeasonInventory, inventory_problems
from nba_data.ml.models import (
    DEFAULT_SPECS,
    MODEL_HOME_RATE,
    SEED,
    SIMPLICITY_ORDER,
    CalibratedModel,
    ModelSpec,
    TrainingSet,
    WinProbabilityModel,
    apply_sigmoid,
    build_model,
    logit,
)
from nba_data.ml.splits import (
    CALIBRATION_SEASON,
    FIRST_HISTORY_SEASON,
    FIRST_TRAINING_SEASON,
    SELECTION_SEASON,
    TEST_SEASON,
    VALIDATION_SEASONS,
    WINDOWS,
    TrainingWindow,
    history_start,
    training_seasons,
)
from nba_data.ml.team_features import (
    FEATURE_DEFINITION_VERSION,
    FEATURE_NAMES,
    TeamFeatureRow,
    build_team_features,
)
from nba_data.ml.team_games import GAME_TYPE_REGULAR_SEASON, TeamGameRecord

BOOTSTRAP_RESAMPLES = 2000
INTERVAL_PERCENTILES = (2.5, 97.5)
CALIBRATION_BINS = 10
PROBABILITY_FLOOR = 1e-15
# Effectively unregularized: a sigmoid has two parameters and a season of games.
CALIBRATOR_C = 1e6
REPORT_DECIMALS = 10

GameReader = Callable[[int], list[TeamGameRecord]]


@dataclass(frozen=True)
class EvaluationPlan:
    specs: tuple[ModelSpec, ...] = DEFAULT_SPECS
    resamples: int = BOOTSTRAP_RESAMPLES
    seed: int = SEED
    inventory: Mapping[int, SeasonInventory] = field(default_factory=lambda: GAME_INVENTORY)


@dataclass(frozen=True)
class EvaluationResult:
    report: dict[str, Any]
    model: WinProbabilityModel
    metadata: dict[str, Any]


def log_losses(labels: Array, probabilities: Array) -> Array:
    clipped = np.clip(probabilities, PROBABILITY_FLOOR, 1 - PROBABILITY_FLOOR)
    return -(labels * np.log(clipped) + (1 - labels) * np.log(1 - clipped))


def week_blocks(dates: Sequence[date]) -> Array:
    """One integer per calendar (ISO) week."""

    weeks = (game_date.isocalendar() for game_date in dates)
    return np.array([week.year * 100 + week.week for week in weeks])


def block_bootstrap_interval(
    values: Array, blocks: Array, *, resamples: int, seed: int
) -> tuple[float, float]:
    """The 95 % interval of the per-game mean, resampling whole blocks."""

    _, block_of_game = np.unique(blocks, return_inverse=True)
    totals = np.bincount(block_of_game, weights=values)
    counts = np.bincount(block_of_game)
    if len(totals) < 2:
        raise ValueError("a block bootstrap needs at least two blocks")
    draws = np.random.default_rng(seed).integers(0, len(totals), (resamples, len(totals)))
    means = totals[draws].sum(axis=1) / counts[draws].sum(axis=1)
    low, high = np.percentile(means, INTERVAL_PERCENTILES)
    return float(low), float(high)


def score_predictions(
    labels: Array,
    probabilities: Array,
    dates: Sequence[date],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    """Every metric for one set of games. A probability of exactly 0.5 picks the home team."""

    if not len(labels):
        raise ValueError("no games to score")
    per_game = {
        "log_loss": log_losses(labels, probabilities),
        "brier": (probabilities - labels) ** 2,
        "accuracy": ((probabilities >= 0.5) == (labels == 1)).astype(float),
    }
    blocks = week_blocks(dates)
    both_outcomes = len(set(labels.tolist())) == 2
    return {
        "games": len(labels),
        **{name: float(values.mean()) for name, values in per_game.items()},
        "roc_auc": float(roc_auc_score(labels, probabilities)) if both_outcomes else None,
        "intervals_95": {
            name: list(block_bootstrap_interval(values, blocks, resamples=resamples, seed=seed))
            for name, values in per_game.items()
        },
    }


def calibration_bins(labels: Array, probabilities: Array) -> list[dict[str, Any]]:
    """Equal-width bins with their sample sizes; an empty bin has no rates."""

    edges = np.linspace(0.0, 1.0, CALIBRATION_BINS + 1)
    bin_of_game = np.minimum((probabilities * CALIBRATION_BINS).astype(int), CALIBRATION_BINS - 1)
    bins = []
    for index in range(CALIBRATION_BINS):
        members = bin_of_game == index
        count = int(members.sum())
        bins.append(
            {
                "low": float(edges[index]),
                "high": float(edges[index + 1]),
                "games": count,
                "mean_predicted": float(probabilities[members].mean()) if count else None,
                "observed_home_win_rate": float(labels[members].mean()) if count else None,
            }
        )
    return bins


@dataclass(frozen=True)
class SelectionStep:
    challenger: str
    incumbent: str
    mean_log_loss_difference: float
    interval_95: tuple[float, float]
    replaced: bool


@dataclass(frozen=True)
class Selection:
    model: str
    steps: tuple[SelectionStep, ...]


def select_model(
    per_game_log_loss: dict[str, Array],
    dates: Sequence[date],
    *,
    resamples: int,
    seed: int,
) -> Selection:
    """Walk from simplest to most complex; replace only on a clear gain.

    A challenger displaces the incumbent only when the whole interval of its
    log-loss difference lies below zero, so an indistinguishable pair keeps the
    simpler model.
    """

    ordered = [name for name in SIMPLICITY_ORDER if name in per_game_log_loss]
    if not ordered:
        raise ValueError("no model to select")
    blocks = week_blocks(dates)
    incumbent = ordered[0]
    steps = []
    for challenger in ordered[1:]:
        difference = per_game_log_loss[challenger] - per_game_log_loss[incumbent]
        interval = block_bootstrap_interval(difference, blocks, resamples=resamples, seed=seed)
        replaced = interval[1] < 0
        steps.append(
            SelectionStep(challenger, incumbent, float(difference.mean()), interval, replaced)
        )
        if replaced:
            incumbent = challenger
    return Selection(incumbent, tuple(steps))


def fit_sigmoid(labels: Array, probabilities: Array) -> tuple[float, float]:
    """`(slope, intercept)` of a sigmoid over the logit of `probabilities`."""

    calibrator = LogisticRegression(C=CALIBRATOR_C, max_iter=1000)
    calibrator.fit(logit(probabilities).reshape(-1, 1), labels)
    return float(calibrator.coef_[0][0]), float(calibrator.intercept_[0])


@dataclass(frozen=True)
class _Dataset:
    games: list[TeamGameRecord]
    rows: dict[int, list[TeamFeatureRow]]
    labels: dict[str, int]
    skipped_history_games: dict[str, int]
    null_neutral_as_home: int

    def season(self, season: int) -> tuple[Array, list[date]]:
        rows = self.rows[season]
        labels = np.array([self.labels[row.game_id] for row in rows])
        return labels, [row.game_date for row in rows]


@dataclass(frozen=True)
class _Candidate:
    spec: ModelSpec
    window: TrainingWindow
    folds: dict[int, dict[str, Any]]
    mean_validation_log_loss: float


def run_evaluation(read_games: GameReader, plan: EvaluationPlan | None = None) -> EvaluationResult:
    plan = plan or EvaluationPlan()

    data = _load_dataset(read_games, SELECTION_SEASON, plan)
    candidates = [_validate(spec, window, data, plan) for spec in plan.specs for window in WINDOWS]
    per_window = _best_per_model_and_window(candidates)
    finalists = _finalists(per_window)

    selection_labels, selection_dates = data.season(SELECTION_SEASON)
    selection_entries, predictions = _score_selection_season(per_window, data, plan)
    selection = select_model(
        {
            model: log_losses(selection_labels, predictions[model, candidate.window.name])
            for model, candidate in finalists.items()
        },
        selection_dates,
        resamples=plan.resamples,
        seed=plan.seed,
    )
    selected = finalists[selection.model]
    calibration = _check_calibration(
        selected, predictions[selection.model, selected.window.name], data
    )

    test_data = _load_dataset(read_games, TEST_SEASON, plan)
    _require_same_history(data, test_data)
    test = _run_test(selected, finalists[MODEL_HOME_RATE], calibration, test_data, plan)
    final_model = _with_calibration(
        _fit(selected.spec, selected.window, TEST_SEASON + 1, test_data), calibration
    )

    report = {
        "feature_definition_version": FEATURE_DEFINITION_VERSION,
        "protocol": _protocol_section(plan),
        "dataset": _dataset_section(test_data, plan),
        "validation": [_validation_entry(candidate) for candidate in candidates],
        "selection_season": selection_entries,
        "selection": _selection_section(selection, finalists),
        "calibration": calibration,
        "test": test,
    }
    metadata = {
        "model": selection.model,
        "feature_definition_version": FEATURE_DEFINITION_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "training_window": selected.window.name,
        "training_seasons": list(training_seasons(TEST_SEASON + 1, selected.window)),
        "configuration": selected.spec.configuration,
        "metrics": {
            "mean_validation_log_loss": selected.mean_validation_log_loss,
            "test": test["selected"]["metrics"],
            "home_rate_test_log_loss": test["home_rate_baseline"]["metrics"]["log_loss"],
            "stage_5_go": test["stage_5_go"],
        },
        "calibration": calibration,
        "seed": plan.seed,
        "scikit_learn_version": sklearn.__version__,
    }
    return EvaluationResult(_rounded(report), final_model, _rounded(metadata))


def report_text(report: dict[str, Any], artifact: SavedArtifact) -> str:
    document = {**report, "artifact": {"directory": artifact.path.name, "sha12": artifact.sha12}}
    return json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"


def run_and_publish(
    read_games: GameReader,
    *,
    output: Path,
    artifact_dir: Path,
    plan: EvaluationPlan | None = None,
) -> dict[str, Any]:
    """Run the protocol, save the artifact, write the report, return a short summary."""

    result = run_evaluation(read_games, plan)
    artifact = save_artifact(result.model, result.metadata, artifact_dir)
    publish_text(output, report_text(result.report, artifact))
    test = result.report["test"]
    return {
        "selected": result.report["selection"]["selected"],
        "why": result.report["selection"]["why"],
        "calibrated": result.report["calibration"]["kept"],
        "test_log_loss": test["selected"]["metrics"]["log_loss"],
        "home_rate_test_log_loss": test["home_rate_baseline"]["metrics"]["log_loss"],
        "stage_5_go": test["stage_5_go"],
        "artifact": artifact.path.name,
        "report": str(output),
    }


def _load_dataset(read_games: GameReader, through_season: int, plan: EvaluationPlan) -> _Dataset:
    games = read_games(through_season)
    later = sorted({game.season_year for game in games if game.season_year > through_season})
    if later:
        raise ValueError(f"reader returned seasons after {through_season}: {later}")
    problems = inventory_problems(
        games, range(FIRST_HISTORY_SEASON, through_season + 1), plan.inventory
    )
    if problems:
        raise ValueError("incomplete game data: " + "; ".join(problems))

    seasons = range(FIRST_TRAINING_SEASON, through_season + 1)
    targets = [
        game
        for game in games
        if game.game_type == GAME_TYPE_REGULAR_SEASON and game.season_year in seasons
    ]
    build = build_team_features(games, target_ids=[game.game_id for game in targets])

    rows: dict[int, list[TeamFeatureRow]] = {season: [] for season in seasons}
    for row in build.rows:
        rows[row.season_year].append(row)

    return _Dataset(
        games=games,
        rows=rows,
        labels={game.game_id: int(_home_won(game)) for game in targets},
        skipped_history_games=build.skipped_games,
        null_neutral_as_home=build.null_neutral_as_home,
    )


def _require_same_history(selected_on: _Dataset, tested_on: _Dataset) -> None:
    """Selection and the test must rest on one history, whatever the reader guarantees."""

    last_season = max(game.season_year for game in selected_on.games)
    reread = [game for game in tested_on.games if game.season_year <= last_season]
    if reread != selected_on.games:
        raise ValueError("the game history changed between selection and the test")


def _home_won(game: TeamGameRecord) -> bool:
    assert game.home.pts is not None and game.away.pts is not None
    return game.home.pts > game.away.pts


def _fit(
    spec: ModelSpec, window: TrainingWindow, target_season: int, data: _Dataset
) -> WinProbabilityModel:
    """Fit on the seasons the window allows before `target_season`, and nothing later."""

    rows = [row for season in training_seasons(target_season, window) for row in data.rows[season]]
    first_history = history_start(target_season, window)
    training = TrainingSet(
        rows=rows,
        labels=[data.labels[row.game_id] for row in rows],
        history=[game for game in data.games if first_history <= game.season_year < target_season],
    )
    return build_model(spec).fit(training)


def _predict_season(model: WinProbabilityModel, season: int, data: _Dataset) -> Array:
    model.observe(game for game in data.games if game.season_year == season)
    return np.asarray(model.predict_proba(data.rows[season]), dtype=float)


def _validate(
    spec: ModelSpec, window: TrainingWindow, data: _Dataset, plan: EvaluationPlan
) -> _Candidate:
    folds = {}
    for season in VALIDATION_SEASONS:
        labels, dates = data.season(season)
        probabilities = _predict_season(_fit(spec, window, season, data), season, data)
        folds[season] = {
            **score_predictions(
                labels, probabilities, dates, resamples=plan.resamples, seed=plan.seed
            ),
            "calibration_bins": calibration_bins(labels, probabilities),
        }
    mean = float(np.mean([fold["log_loss"] for fold in folds.values()]))
    return _Candidate(spec, window, folds, mean)


def _best_per_model_and_window(
    candidates: Iterable[_Candidate],
) -> dict[tuple[str, str], _Candidate]:
    best: dict[tuple[str, str], _Candidate] = {}
    for candidate in candidates:
        key = (candidate.spec.model, candidate.window.name)
        if key not in best or candidate.mean_validation_log_loss < (
            best[key].mean_validation_log_loss
        ):
            best[key] = candidate
    return best


def _finalists(per_window: dict[tuple[str, str], _Candidate]) -> dict[str, _Candidate]:
    """Each model's best configuration, window included."""

    finalists: dict[str, _Candidate] = {}
    for (model, _), candidate in per_window.items():
        current = finalists.get(model)
        if current is None or candidate.mean_validation_log_loss < (
            current.mean_validation_log_loss
        ):
            finalists[model] = candidate
    return finalists


def _score_selection_season(
    per_window: dict[tuple[str, str], _Candidate], data: _Dataset, plan: EvaluationPlan
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], Array]]:
    labels, dates = data.season(SELECTION_SEASON)
    entries = []
    predictions = {}
    for key, candidate in per_window.items():
        model = _fit(candidate.spec, candidate.window, SELECTION_SEASON, data)
        probabilities = _predict_season(model, SELECTION_SEASON, data)
        predictions[key] = probabilities
        entries.append(
            {
                "model": candidate.spec.model,
                "window": candidate.window.name,
                "configuration": candidate.spec.configuration,
                "mean_validation_log_loss": candidate.mean_validation_log_loss,
                "metrics": score_predictions(
                    labels, probabilities, dates, resamples=plan.resamples, seed=plan.seed
                ),
                "calibration_bins": calibration_bins(labels, probabilities),
            }
        )
    return entries, predictions


def _check_calibration(
    selected: _Candidate, selection_probabilities: Array, data: _Dataset
) -> dict[str, Any]:
    """Fit on the 2024 fold; keep only if the sigmoid lowers log loss on 2025."""

    fold_labels, _ = data.season(CALIBRATION_SEASON)
    model = _fit(selected.spec, selected.window, CALIBRATION_SEASON, data)
    slope, intercept = fit_sigmoid(fold_labels, _predict_season(model, CALIBRATION_SEASON, data))

    labels, _ = data.season(SELECTION_SEASON)
    raw = float(log_losses(labels, selection_probabilities).mean())
    calibrated = float(
        log_losses(labels, apply_sigmoid(selection_probabilities, slope, intercept)).mean()
    )
    return {
        "method": "sigmoid",
        "fitted_on_season": CALIBRATION_SEASON,
        "checked_on_season": SELECTION_SEASON,
        "slope": slope,
        "intercept": intercept,
        "raw_log_loss": raw,
        "calibrated_log_loss": calibrated,
        "kept": calibrated < raw,
    }


def _with_calibration(
    model: WinProbabilityModel, calibration: dict[str, Any]
) -> WinProbabilityModel:
    if not calibration["kept"]:
        return model
    return CalibratedModel(model, calibration["slope"], calibration["intercept"])


def _run_test(
    selected: _Candidate,
    baseline: _Candidate,
    calibration: dict[str, Any],
    data: _Dataset,
    plan: EvaluationPlan,
) -> dict[str, Any]:
    """The single look at the test season. Go needs a win over the home-rate baseline."""

    labels, dates = data.season(TEST_SEASON)
    contenders = (
        (
            "selected",
            _with_calibration(_fit(selected.spec, selected.window, TEST_SEASON, data), calibration),
        ),
        ("home_rate_baseline", _fit(baseline.spec, baseline.window, TEST_SEASON, data)),
    )
    results: dict[str, dict[str, Any]] = {}
    for name, model in contenders:
        probabilities = _predict_season(model, TEST_SEASON, data)
        results[name] = {
            "metrics": score_predictions(
                labels, probabilities, dates, resamples=plan.resamples, seed=plan.seed
            ),
            "calibration_bins": calibration_bins(labels, probabilities),
        }
    selected_loss = results["selected"]["metrics"]["log_loss"]
    baseline_loss = results["home_rate_baseline"]["metrics"]["log_loss"]
    return {**results, "stage_5_go": selected_loss < baseline_loss}


def _protocol_section(plan: EvaluationPlan) -> dict[str, Any]:
    targets = (*VALIDATION_SEASONS, SELECTION_SEASON, TEST_SEASON)
    return {
        "seed": plan.seed,
        "bootstrap_resamples": plan.resamples,
        "first_history_season": FIRST_HISTORY_SEASON,
        "first_training_season": FIRST_TRAINING_SEASON,
        "validation_seasons": list(VALIDATION_SEASONS),
        "calibration_season": CALIBRATION_SEASON,
        "selection_season": SELECTION_SEASON,
        "test_season": TEST_SEASON,
        "windows": {window.name: window.seasons for window in WINDOWS},
        "training_seasons_by_target": {
            str(season): {window.name: list(training_seasons(season, window)) for window in WINDOWS}
            for season in targets
        },
    }


def _dataset_section(data: _Dataset, plan: EvaluationPlan) -> dict[str, Any]:
    targets = {row.game_id for rows in data.rows.values() for row in rows}
    history_only: dict[str, list[str]] = {}
    for game in data.games:
        if game.game_id not in targets:
            history_only.setdefault(str(game.season_year), []).append(game.game_id)
    seasons = range(FIRST_HISTORY_SEASON, TEST_SEASON + 1)
    return {
        "input_sha256": _input_fingerprint(data.games),
        "history_games": len(data.games),
        "history_only_game_ids_by_season": history_only,
        "skipped_history_games_by_feature": data.skipped_history_games,
        "null_neutral_as_home": data.null_neutral_as_home,
        "skipped_target_game_ids": sorted(
            game_id for season in seasons for game_id in plan.inventory[season].quarantined
        ),
        "game_ids_by_season": {
            str(season): [row.game_id for row in rows] for season, rows in sorted(data.rows.items())
        },
    }


def _input_fingerprint(games: list[TeamGameRecord]) -> str:
    """The SHA-256 of every field the evaluation read, in reading order."""

    document = json.dumps([asdict(game) for game in games], default=str, sort_keys=True)
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def _validation_entry(candidate: _Candidate) -> dict[str, Any]:
    return {
        "model": candidate.spec.model,
        "window": candidate.window.name,
        "configuration": candidate.spec.configuration,
        "folds": {str(season): metrics for season, metrics in candidate.folds.items()},
        "mean_log_loss": candidate.mean_validation_log_loss,
    }


def _selection_section(selection: Selection, finalists: dict[str, _Candidate]) -> dict[str, Any]:
    return {
        "finalists": {
            model: {
                "window": finalists[model].window.name,
                "configuration": finalists[model].spec.configuration,
                "mean_validation_log_loss": finalists[model].mean_validation_log_loss,
            }
            for model in SIMPLICITY_ORDER
            if model in finalists
        },
        "steps": [
            {
                "challenger": step.challenger,
                "incumbent": step.incumbent,
                "mean_log_loss_difference": step.mean_log_loss_difference,
                "interval_95": list(step.interval_95),
                "replaced": step.replaced,
            }
            for step in selection.steps
        ],
        "selected": selection.model,
        "why": _selection_reason(selection),
    }


def _selection_reason(selection: Selection) -> str:
    replacements = [step for step in selection.steps if step.replaced]
    if not replacements:
        return f"no more complex model cleared the 95 % interval against {selection.model}"
    last = replacements[-1]
    return (
        f"{last.challenger} replaced {last.incumbent}: its log-loss difference on "
        f"{SELECTION_SEASON} lies entirely below zero, and no more complex model improved on it"
    )


def _rounded(value: Any) -> Any:
    """Bounded float noise, so the report does not depend on the last bits."""

    if isinstance(value, float):
        return round(value, REPORT_DECIMALS)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_rounded(item) for item in value]
    return value
