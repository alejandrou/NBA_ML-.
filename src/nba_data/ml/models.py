"""The four candidates behind one interface.

`predict_proba(rows)` returns each row's home-win probability; the away side is
its complement. Elo needs results the rows do not carry, so a caller feeds it
the target season's games through `observe`; it reads only those dated at or
before each row's results cutoff.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Protocol

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nba_data.ml._numpy import Array, np
from nba_data.ml.elo import EloRatings, expected_home_win, home_advantage
from nba_data.ml.team_features import FEATURE_NAMES, RESULTS_CUTOFF_DAYS, TeamFeatureRow
from nba_data.ml.team_games import TeamGameRecord

SEED = 20261018

MODEL_HOME_RATE = "home-rate"
MODEL_ELO = "elo"
MODEL_LOGISTIC = "logistic"
MODEL_BOOSTING = "boosting"
# Simplest first: a later model must earn its place against an earlier one.
SIMPLICITY_ORDER = (MODEL_HOME_RATE, MODEL_ELO, MODEL_LOGISTIC, MODEL_BOOSTING)

LOGISTIC_MAX_ITER = 5000
BOOSTING_MAX_ITER = 300


@dataclass(frozen=True)
class TrainingSet:
    rows: Sequence[TeamFeatureRow]
    # 1 when the home team won, aligned with `rows`.
    labels: Sequence[int]
    # The window's finished games, for a model that keeps its own memory.
    history: Sequence[TeamGameRecord]


class WinProbabilityModel(Protocol):
    name: str

    def fit(self, training: TrainingSet) -> WinProbabilityModel: ...

    def observe(self, games: Iterable[TeamGameRecord]) -> None: ...

    def predict_proba(self, rows: Sequence[TeamFeatureRow]) -> list[float]: ...


@dataclass(frozen=True)
class ModelSpec:
    model: str
    configuration: dict[str, Any] = field(default_factory=dict)


class HomeRateModel:
    """The training home-win rate on a home floor, a coin flip on a neutral one."""

    name = MODEL_HOME_RATE

    def __init__(self) -> None:
        self.home_rate: float | None = None

    def fit(self, training: TrainingSet) -> HomeRateModel:
        home_floor = [
            label
            for row, label in zip(training.rows, training.labels, strict=True)
            if not row.values["is_neutral"]
        ]
        if not home_floor:
            raise ValueError("the home-rate model needs a game on a home floor")
        self.home_rate = sum(home_floor) / len(home_floor)
        return self

    def observe(self, games: Iterable[TeamGameRecord]) -> None:
        """The rate is fixed by training; a season in progress does not move it."""

    def predict_proba(self, rows: Sequence[TeamFeatureRow]) -> list[float]:
        if self.home_rate is None:
            raise ValueError("the home-rate model is not fitted")
        return [0.5 if row.values["is_neutral"] else self.home_rate for row in rows]


class EloModel:
    """`1 / (1 + 10^(−diff/400))`, with its own K and home advantage."""

    name = MODEL_ELO

    def __init__(self, k: float, home_points: float) -> None:
        self.k = k
        self.home_points = home_points
        self._games: dict[str, TeamGameRecord] = {}

    def fit(self, training: TrainingSet) -> EloModel:
        self._games = {}
        self.observe(training.history)
        return self

    def observe(self, games: Iterable[TeamGameRecord]) -> None:
        for game in games:
            if game.home.pts is not None and game.away.pts is not None:
                self._games[game.game_id] = game

    def predict_proba(self, rows: Sequence[TeamFeatureRow]) -> list[float]:
        scored = sorted(self._games.values(), key=lambda game: (game.game_date, game.game_id))
        ratings = EloRatings(self.k, self.home_points)
        probabilities = [0.0] * len(rows)
        position = 0
        for index in sorted(range(len(rows)), key=lambda at: rows[at].game_date):
            row = rows[index]
            cutoff = row.game_date - timedelta(days=RESULTS_CUTOFF_DAYS)
            while position < len(scored) and scored[position].game_date <= cutoff:
                ratings.update(scored[position])
                position += 1
            probabilities[index] = expected_home_win(
                ratings.pregame(row.home_team, row.season_year),
                ratings.pregame(row.away_team, row.season_year),
                home_advantage(row.values["is_neutral"] is True, self.home_points),
            )
        return probabilities


class SklearnModel:
    """A pipeline fitted on the ordered `team-pregame-v1` values; blanks are `NaN`."""

    def __init__(self, name: str, estimator: Any) -> None:
        self.name = name
        self.estimator = estimator
        self.feature_names = FEATURE_NAMES

    def fit(self, training: TrainingSet) -> SklearnModel:
        self.estimator.fit(self._matrix(training.rows), np.asarray(training.labels))
        return self

    def observe(self, games: Iterable[TeamGameRecord]) -> None:
        """Every value it reads is already in the rows."""

    def predict_proba(self, rows: Sequence[TeamFeatureRow]) -> list[float]:
        home_column = list(self.estimator.classes_).index(1)
        probabilities = self.estimator.predict_proba(self._matrix(rows))[:, home_column]
        return [float(probability) for probability in probabilities]

    def _matrix(self, rows: Sequence[TeamFeatureRow]) -> Array:
        return np.array(
            [[row.values[name] for name in self.feature_names] for row in rows],
            dtype=float,
        )


class CalibratedModel:
    """A fitted model with a sigmoid over the logit of its probability."""

    def __init__(self, base: WinProbabilityModel, slope: float, intercept: float) -> None:
        self.base = base
        self.name = base.name
        self.slope = slope
        self.intercept = intercept

    def fit(self, training: TrainingSet) -> CalibratedModel:
        self.base.fit(training)
        return self

    def observe(self, games: Iterable[TeamGameRecord]) -> None:
        self.base.observe(games)

    def predict_proba(self, rows: Sequence[TeamFeatureRow]) -> list[float]:
        probabilities = np.asarray(self.base.predict_proba(rows), dtype=float)
        return apply_sigmoid(probabilities, self.slope, self.intercept).tolist()


def logit(probabilities: Array) -> Array:
    clipped = np.clip(probabilities, 1e-15, 1 - 1e-15)
    return np.log(clipped / (1 - clipped))


def apply_sigmoid(probabilities: Array, slope: float, intercept: float) -> Array:
    return 1.0 / (1.0 + np.exp(-(slope * logit(probabilities) + intercept)))


def build_model(spec: ModelSpec) -> WinProbabilityModel:
    configuration = spec.configuration
    if spec.model == MODEL_HOME_RATE:
        return HomeRateModel()
    if spec.model == MODEL_ELO:
        return EloModel(configuration["k"], configuration["home_advantage"])
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    if spec.model == MODEL_LOGISTIC:
        return SklearnModel(
            MODEL_LOGISTIC,
            make_pipeline(
                imputer,
                StandardScaler(),
                LogisticRegression(
                    C=configuration["c"], max_iter=LOGISTIC_MAX_ITER, random_state=SEED
                ),
            ),
        )
    if spec.model == MODEL_BOOSTING:
        return SklearnModel(
            MODEL_BOOSTING,
            make_pipeline(
                imputer,
                HistGradientBoostingClassifier(
                    learning_rate=configuration["learning_rate"],
                    max_depth=configuration["max_depth"],
                    max_iter=BOOSTING_MAX_ITER,
                    early_stopping=False,
                    random_state=SEED,
                ),
            ),
        )
    raise ValueError(f"unknown model: {spec.model}")


DEFAULT_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(MODEL_HOME_RATE),
    *(
        ModelSpec(MODEL_ELO, {"k": k, "home_advantage": points})
        for k in (15, 20, 25)
        for points in (70, 100)
    ),
    *(ModelSpec(MODEL_LOGISTIC, {"c": c}) for c in (0.01, 0.1, 1, 10)),
    *(
        ModelSpec(MODEL_BOOSTING, {"learning_rate": rate, "max_depth": depth})
        for rate in (0.05, 0.1)
        for depth in (3, None)
    ),
)
