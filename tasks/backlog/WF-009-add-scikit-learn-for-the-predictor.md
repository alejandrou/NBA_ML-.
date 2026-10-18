---
id: WF-009
title: Add scikit-learn for the predictor
track: shared
areas:
  - testing
  - documentation
priority: 93
depends_on: []
read:
  - pyproject.toml
  - docs/ml/PREDICTOR_PLAN.md
  - docs/decisions/0018-run-data-and-app-tracks-in-parallel.md
  - tests/unit/test_stats_coverage_artifact.py
validation:
  - uv lock --check
  - uv run pytest tests/unit/test_ml_dependency_boundary.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. `uv lock` resolves packages from PyPI, the normal dependency path; nothing touches Basketball Reference or the database.
---

# Goal

Add `scikit-learn` to the runtime dependencies so the `data` track can fit and
evaluate the Stage 3 models (F8-007), and prove that the API never imports it,
so the `app` track keeps the "no ML dependency" decision of F8-010.

# Evidence and current state

- `pyproject.toml` has no numerical dependency: no numpy, scipy, pandas, or
  scikit-learn. COMP #49 trimmed the runtime list to what the platform imports.
- `docs/ml/PREDICTOR_PLAN.md` §6: a new runtime dependency changes
  `pyproject.toml`/`uv.lock` and is a `shared` card that blocks both tracks.
- F8-010 decided that forecasts are computed by the `data` track and stored, so
  the API reads rows and runs no model.
- The plan's models are a home-rate baseline, Elo, regularized logistic
  regression, and gradient boosting. Elo and the feature builder are plain
  Python (F8-011); `LogisticRegression`, `HistGradientBoostingClassifier`,
  `CalibratedClassifierCV`, and the metrics are scikit-learn.

# Human decisions or resources

- [x] **Add `scikit-learn` and nothing else** (decided 2026-10-18). It brings
      `numpy`, `scipy`, `joblib`, and `threadpoolctl`. No pandas (the feature
      builder works on plain records), no XGBoost or LightGBM
      (`HistGradientBoostingClassifier` covers boosting), no matplotlib (the
      report is JSON and Markdown).
- [x] **A runtime dependency, not an optional extra.** The `nba-data ml`
      commands live in the same package and CLI; an extra would make
      `uv sync` and CI differ by flag. The boundary is enforced by a test, not
      by packaging.
- [x] **Lower bound `scikit-learn>=1.5`**; the version `uv lock` resolves is
      the pin. It must install as a wheel on Python 3.12 (CI) and on the
      owner's local interpreter; if `uv lock` cannot satisfy both, stop and
      report rather than loosening the bound.

# Acceptance criteria

- `pyproject.toml` lists `scikit-learn>=1.5` in `[project].dependencies`, in
  alphabetical order, with a one-line comment that it serves `nba_data.ml` only.
- `uv.lock` is regenerated with `uv lock`; `uv lock --check` passes; `uv sync`
  and the full suite pass on Python 3.12 as CI runs it.
- `tests/unit/test_ml_dependency_boundary.py` (new): walks every module under
  `src/nba_data/api/` and `src/nba_data/db/repositories/queries/` with `ast` and
  fails if any imports `sklearn`, `numpy`, `scipy`, `joblib`, or
  `nba_data.ml`. A second test imports `nba_data.api.app` in a subprocess and
  asserts none of those modules is in `sys.modules`.
- No source module imports scikit-learn yet; that is F8-007.

# Scope

`pyproject.toml`, `uv.lock`, `tests/unit/test_ml_dependency_boundary.py`,
`docs/ml/PREDICTOR_PLAN.md` (§6: the dependency is added),
`docs/architecture/API_ARCHITECTURE.md` (the import boundary).

# Out of scope

Any model, feature, or CLI code. Any other dependency. CI workflow changes.

# Impact

- Both worktrees run `uv sync --all-groups` after this merges.

# Cross-track impact

- `shared`: it holds both slots while active. The `app` track gains a test
  that forbids ML imports under `nba_data.api`.

# Implementation notes

- Run it when both tracks are idle: `Start the next task.` picks a `shared`
  card only then.
- Model the boundary test on
  `test_stats_coverage_has_no_database_or_network_import_anywhere_in_its_dependency_graph`
  (`tests/unit/test_stats_coverage_artifact.py:174`).

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` §6 and `docs/architecture/API_ARCHITECTURE.md`.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
