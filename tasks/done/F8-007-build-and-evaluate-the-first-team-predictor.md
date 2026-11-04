---
id: F8-007
title: Build and evaluate the first team predictor
track: data
areas:
  - ml
  - database-read
  - testing
  - documentation
priority: 92
depends_on:
  - F8-011
  - F8-018
  - WF-009
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/ml/team_features.py
  - src/nba_data/ml/elo.py
  - src/nba_data/ml/team_games.py
  - src/nba_data/cli/main.py
validation:
  - uv run pytest tests/unit/test_ml_splits.py tests/unit/test_ml_models.py tests/unit/test_ml_evaluation.py tests/unit/test_ml_artifact.py tests/unit/test_cli_ml.py tests/unit/test_ml_dependency_boundary.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run nba-data ml evaluate --output reports/ml/f8-007/evaluation.json --artifact-dir data/models
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. Evaluation reads the persistent nba database and writes only `reports/` and `data/models/`, both uncommitted; no scrape, no write to the database.
---

# Goal

Answer Stage 3's question with a measured, reproducible result: on later
seasons, which of home-rate, Elo, regularized logistic regression, and gradient
boosting gives the best pre-game win probabilities at the 24-hour horizon? Fit
the selected one, save it as a versioned artifact, and record the result.
`F8-010` stores its forecasts; `F6-021` serves them.

# Evidence and current state

- `docs/ml/PREDICTOR_PLAN.md` Stage 3 fixes the models, the splits, the
  training windows (3, 5, all seasons), the metrics (log loss primary; Brier,
  calibration, accuracy, ROC-AUC), separate calibration, temporal-block
  intervals, "indistinguishable keeps the simpler", and a test season used once.
- F8-006 acquired 2014-15 to 2025-26 (end years 2015 to 2026) and loaded it on
  a disposable database; F8-018 loads it into `nba`. F8-011 builds the
  `team-pregame-v1` features and Elo. WF-009 adds scikit-learn.
- No `features` or `ml` table exists; F8-010 adds `ml.*` after this card.

# Human decisions or resources

- [x] **scikit-learn through `WF-009`** (decided 2026-10-18): scikit-learn only;
      no pandas, no XGBoost.
- [x] **Cutoff without time zones**: results-based features use only games
      dated at least two days before the target game; schedule features use the
      published schedule. Never later than tip-off − 24 h, no tzdata (F8-002).
- [x] **Training set**: `game_type = 'regular_season'` only. Neutral games kept
      with home advantage zeroed; `NULL` neutral treated as home.
- [x] **No `features` or `ml` tables here.** Features are computed in memory;
      the report goes to `reports/ml/` and a dated summary to `docs/ml/`.
- [x] **Splits** (end years): test = 2026; calibration and selection = 2025;
      rolling validation folds = train on seasons before Y, validate on Y, for
      Y = 2020 to 2024. Windows: last 3, last 5, all available seasons before
      the validated one. 2015 games are history only (every team's Elo starts
      there), never a validation target.
- [x] **Models and grids**, each fitted inside its training split only
      (imputation by training median, standardization for logistic regression):
      home-rate baseline (training home-win rate; 0.5 on neutral games); Elo
      probability `1 / (1 + 10^(−diff/400))` with K in {15, 20, 25} and home
      advantage in {70, 100}; `LogisticRegression` L2, C in
      {0.01, 0.1, 1, 10}; `HistGradientBoostingClassifier` with
      learning_rate {0.05, 0.1}, max_depth {3, None}, max_iter 300,
      early stopping off. Seeds fixed at 20261018.
- [x] **Selection rule**, fixed before any number is seen: each model's best
      configuration is the one with the lowest mean validation log loss over
      the five folds; models are then compared on season 2025. Simplicity order
      home-rate < Elo < logistic < boosting. A more complex model replaces a
      simpler one only when the 95 % interval of its log-loss difference on
      2025, from a block bootstrap over calendar weeks (2,000 resamples), lies
      entirely below 0.
- [x] **Calibration**: for the selected model, a sigmoid calibrator is fitted
      on its 2024-fold predictions (model trained on seasons before 2024) and
      kept only if applying it to the 2025 predictions lowers 2025 log loss —
      fitted apart from training and kept only if it improves later data, per
      the plan. Sigmoid, not isotonic: one season (~1,230 games) is too few
      for a stable isotonic fit.
- [x] **Test once**: the selected, possibly calibrated model is refitted on all
      seasons up to 2025 with its window and scored on 2026 a single time. The
      report records the test result whatever it is.
- [x] **Go for Stage 5**: `F8-010` starts only if the selected model beats the
      home-rate baseline's 2026 log loss. Otherwise the result is recorded in
      `docs/ml/` and F8-010 stays blocked; no forecast is published.
- [x] **Artifact**: after the test, the selected model is refitted on every
      season up to 2026 and saved as
      `data/models/<model>-team-pregame-v1-<sha12>/` with `model.joblib` and
      `metadata.json` (model name, feature-definition version, ordered feature
      names, training window and seasons, configuration, metrics, calibration,
      seed, scikit-learn version, and the SHA-256 of `model.joblib`; `sha12` is
      its first 12 hex characters). Elo and home-rate are saved through the
      same interface, so F8-010 loads any winner the same way.

# Acceptance criteria

- `src/nba_data/ml/`: `splits.py` (folds and windows by season end year),
  `models.py` (one `predict_proba(rows) -> list[float]` interface returning the
  home-win probability for each model), `evaluation.py` (metrics, block
  bootstrap, selection, calibration check), `artifact.py` (save and load with
  the SHA-256 check; loading refuses a hash mismatch).
- `nba-data ml evaluate --output <json> --artifact-dir <dir>`: reads through
  `team_games.py`, runs the whole protocol, writes the report, and saves the
  artifact. Rerunning on the same data gives a byte-identical report and the
  same `sha12`.
- The report holds, per model and window: per-fold and 2025 metrics with
  intervals, sample sizes, calibration bins with counts, the selected model and
  why, the 2026 test metrics, the exact game ids of every split, the skipped
  games, and the feature-definition version.
- Unit tests on synthetic seasons: splits never overlap and never put a later
  season in training; every model is scored on the same games; probabilities
  are in [0, 1] and home + away = 1; the selection rule picks the simpler model
  on an indistinguishable pair and the complex one on a clear gain; the test
  season is read only after selection (a spy proves it); the artifact
  round-trips and refuses a changed byte.
- `docs/ml/TEAM_PREDICTOR_EVALUATION.md` (new, dated) summarizes the result;
  `PREDICTOR_PLAN.md` Stage 3 records it.

# Scope

`src/nba_data/ml/` (new modules above), `src/nba_data/cli/main.py` (the `ml`
group and `evaluate`), `tests/unit/test_ml_*.py`, `tests/unit/test_cli_ml.py`,
`docs/ml/`.

# Out of scope

Player features (F8-009). Tables, revisions, `ml predict`, and model
registration (F8-010). Any scrape or database write. Changing
`team-pregame-v1`; a change there is a new F8-011-style card.

# Impact

- New `nba-data ml evaluate` command; offline over the loaded tables.

# Cross-track impact

- None.

# Implementation notes

- Run `ml evaluate` against `nba` only after F8-018 has loaded it. On review,
  the reviewer may rerun it; it only reads.
- joblib files are pickles: load only artifacts this repository wrote, after
  the hash check.

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — the Stage 3 result, dated.
- `docs/ml/TEAM_PREDICTOR_EVALUATION.md` (new).

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_ml_splits.py tests/unit/test_ml_models.py tests/unit/test_ml_evaluation.py tests/unit/test_ml_artifact.py tests/unit/test_cli_ml.py tests/unit/test_ml_dependency_boundary.py`
- Result: pass (run as part of the full suite below, and before it).
- Command: `uv run ruff check .`
- Result: all checks passed.
- Command: `uv run mypy src/nba_data`
- Result: no issues in 104 source files, with numpy kept opaque by `src/nba_data/ml/_numpy.py` (see Known limitations).
- Command: `uv run pytest`
- Result: 1694 passed, 258 skipped (integration, covered by the next command).
- Command: `bash scripts/validate_database.sh`
- Result: 259 integration tests passed on a temporary database, which was then dropped.
- Command: `uv run nba-data ml evaluate --output reports/ml/f8-007/evaluation-2.json --artifact-dir data/models` (against `nba`, one read-only `REPEATABLE READ` transaction, run twice after the review fixes; `SHOW` confirmed `repeatable read` and `transaction_read_only = on`)
- Result: selected logistic (C 0.01, last 5), calibrated; test log loss 0.6012 against home-rate 0.6874; Stage 5 go. Both runs: report SHA-256 `f0968b863e78...`, input SHA-256 `95d297abaf04...`, artifact `logistic-team-pregame-v1-f369530d6c6e`. Compared with the pre-fix `evaluation.json` (`6aa21d157792...`, kept): selection, calibration, test, every validation metric, and the artifact are unchanged; only the added report fields differ.
- Command: `uv run python scripts/validate_tasks.py`
- Result: passed after the move to `tasks/review/`.

## Manual happy path

1. `uv run nba-data ml evaluate --output reports/ml/f8-007/rerun.json --artifact-dir data/models`
2. Compare `reports/ml/f8-007/rerun.json` with `evaluation-2.json`.
3. Read `docs/ml/TEAM_PREDICTOR_EVALUATION.md` against the report's `selection` and `test` sections.

Expected result: the two reports are byte-identical, `data/models/` still holds one directory, and the summary shows `logistic`, `stage_5_go: true`.

## Manual sad path

1. Flip one byte of `data/models/logistic-team-pregame-v1-f369530d6c6e/model.joblib` on a copy of the directory, then call `load_artifact` on the copy.
2. Edit one character of a copy of `reports/ml/f8-007/evaluation-2.json`, then rerun the command in the happy path with `--output` at that copy.
3. Run the command with `DATABASE_URL` pointing at a disposable database holding only part of a season.

Expected result: (1) `ArtifactIntegrityError`, nothing unpickled; (2) exit 1, "exists with different content", the file untouched; (3) exit 1, "incomplete game data: season ...: N scored regular-season games, expected M", no report and no artifact.

## Known limitations

- The test season was scored in five runs, all after selection: two before the review fixes and three after (the third proved the refusal to replace `evaluation.json`). The fixes changed no selection input, and every number stayed the same. A later protocol change needs a new test season.
- `nba_data.ml.inventory` hard-codes the 2015-2026 counts and the 7 quarantines from `docs/validation/GAME_DATASET_ACQUISITION.md`. A reload that resolves a quarantine must update it, or the evaluation stops.
- A game with a blank score now stops the evaluation instead of being skipped, so `skipped_target_game_ids` lists the 7 documented quarantines.
- numpy 2.5's stubs are newer than `[tool.mypy] python_version = "3.11"`, which stops mypy. Fixing that belongs to `pyproject.toml` (shared track), so `ml/_numpy.py` hides numpy from mypy instead. It also means `numpy` and `joblib` are imported directly while reaching the project only through scikit-learn. A shared card should raise the mypy target, declare both, and delete the shim.
- The readings the card left open (2015 not a training row, Elo's window, the home rate on home floors, the artifact's window) are recorded in the evaluation document.
- Logistic chose the edge of its grid (C = 0.01). The grid is fixed for this card; a smaller C would be a later experiment on a new test season.
- Calibration's gain on 2025 was 0.00016 of log loss: kept by rule, not by size.
- Outside the card's stated scope: `.gitignore` gains `data/models/` (it was not ignored); `elo.py` takes optional `k` and home-points overrides whose defaults keep `team-pregame-v1` unchanged; `load_team_game_history` gains `through_season`; `src/nba_data/ml/inventory.py` is new (review finding); `test_the_ml_package_imports_no_numeric_library` now guards the three feature modules, since this card puts scikit-learn in the package.
