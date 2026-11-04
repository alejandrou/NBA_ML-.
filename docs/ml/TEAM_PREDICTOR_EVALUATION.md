# Team predictor evaluation — 2026-11-04

Stage 3's result (`F8-007`). The selected model is a calibrated logistic
regression. On the 2025–26 test season its log loss was **0.6012** against the
home-rate baseline's **0.6874**, so Stage 5 (`F8-010`) goes ahead.

Reproduce with `uv run nba-data ml evaluate --output <json> --artifact-dir
<dir>`. It reads the `nba` database in one read-only `REPEATABLE READ`
transaction. Two runs gave a byte-identical report (SHA-256 `f0968b863e78…`) and
the same artifact, `logistic-team-pregame-v1-f369530d6c6e`. The report is
`evaluation-2.json`, over input data with SHA-256 `95d297abaf04…`. The report and
the artifact are local and uncommitted, under `reports/ml/f8-007/` and
`data/models/`.

## Data

- Features: `team-pregame-v1`. 14,435 history games from end years 2015 to 2026;
  regular-season targets from 2016 to 2026.
- Every season matched `nba_data.ml.inventory`, the expected counts less the 7
  documented quarantines. Any other difference stops the evaluation before a
  result exists, and a game with a blank score counts as missing.
- No history game was skipped by any feature, and no game had an undetermined
  `neutral_site`.
- The 7 quarantined games are absent from `core.games`; see the feature
  definition's known limitation in `PREDICTOR_PLAN.md`.

## Selection

Each model's best configuration is its lowest mean validation log loss over the
2020 to 2024 folds; the window is part of that configuration.

| Model | Window | Configuration | Validation log loss | 2025 log loss (95 % interval) | 2025 accuracy | 2025 ROC-AUC |
|---|---|---|---|---|---|---|
| Home rate | last 3 | — | 0.6888 | 0.6895 (0.6824–0.6963) | 0.544 | 0.501 |
| Elo | last 3 | K 20, home 70 | 0.6347 | 0.6120 (0.5949–0.6292) | 0.668 | 0.723 |
| Logistic | last 5 | C 0.01 | 0.6313 | 0.6029 (0.5859–0.6193) | 0.678 | 0.732 |
| Boosting | all | rate 0.05, depth 3 | 0.6398 | 0.6110 (0.5918–0.6309) | 0.661 | 0.724 |

A more complex model replaces a simpler one only when the 95 % interval of its
log-loss difference on 2025 lies entirely below zero.

| Challenger | Incumbent | Mean difference | 95 % interval | Result |
|---|---|---|---|---|
| Elo | Home rate | −0.0774 | −0.0946 to −0.0603 | replaced |
| Logistic | Elo | −0.0091 | −0.0153 to −0.0025 | replaced |
| Boosting | Logistic | +0.0081 | +0.00004 to +0.0162 | kept logistic |

Elo barely depends on its window (validation log loss 0.6347 in all three): a
rating forgets early seasons quickly. Logistic chose the strongest
regularization in its grid, C = 0.01, under every window, so a smaller C could
do better; the grid was fixed in advance and was not widened.

## Calibration

A sigmoid fitted on the 2024 fold (slope 1.141, intercept −0.097) lowered 2025
log loss from 0.60292 to 0.60276, so the rule kept it. The gain is small.

## Test — 2025–26, 1,230 games, scored once

| Model | Log loss (95 % interval) | Brier | Accuracy | ROC-AUC |
|---|---|---|---|---|
| Logistic, calibrated | 0.6012 (0.5704–0.6322) | 0.2072 | 0.672 | 0.731 |
| Home rate | 0.6874 (0.6803–0.6948) | 0.2472 | 0.554 | 0.498 |

Calibration on the test season, as predicted probability against observed home
wins:

| Bin | Games | Mean predicted | Observed |
|---|---|---|---|
| 0.0–0.1 | 8 | 0.082 | 0.000 |
| 0.1–0.2 | 64 | 0.154 | 0.094 |
| 0.2–0.3 | 113 | 0.252 | 0.292 |
| 0.3–0.4 | 177 | 0.353 | 0.384 |
| 0.4–0.5 | 161 | 0.452 | 0.509 |
| 0.5–0.6 | 204 | 0.550 | 0.564 |
| 0.6–0.7 | 203 | 0.649 | 0.704 |
| 0.7–0.8 | 169 | 0.746 | 0.751 |
| 0.8–0.9 | 109 | 0.844 | 0.798 |
| 0.9–1.0 | 22 | 0.921 | 0.955 |

The test log loss is better than every validation fold of this configuration
(0.6075 to 0.6455), and 2025 and 2026 were easier seasons to predict. Treat 0.60
as this season's figure, not the long-run expectation.

## Readings the card left open

Settled before any result existed:

- "2015 is history only" means 2015 games are not training rows either: they
  start from cold ratings. "All seasons" therefore starts at 2016, and `last_5`
  equals `all` for the 2020 and 2021 folds.
- Elo has no fitted parameters, so its window sets where its ratings begin:
  the window's first training season, or 2015 for `all`. Within the target
  season it reads results up to each game's cutoff, as the features do.
- The home-rate model computes its rate on home-floor games only.
- `HistGradientBoostingClassifier` also gets median imputation, though it could
  handle blanks itself.
- The artifact keeps the selected window, so it was trained on 2022 to 2026, with
  the calibrator from the 2024 fold.

## For F8-010

Load the artifact with `nba_data.ml.artifact.load_artifact`, which checks the
hash first. All four model types share `predict_proba(rows)`. Call
`observe(games)` with the season in progress first; only Elo reads it, but the
call is the same for every winner.
