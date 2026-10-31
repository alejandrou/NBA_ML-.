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
- `shared`: it holds both slots while active. The `app` track gains a test
  that forbids ML imports under `nba_data.api` and the query repositories;
  today's app code already passes it, so nothing on the `app` track breaks
  and nothing waits to be adopted.

# Cross-track impact

- None.

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

Run 2026-10-30 on Windows, Python 3.13.6 (the owner's interpreter), in `.venv`:

- `uv lock` → resolved 59 packages; added `scikit-learn` 1.9.1, `numpy`
  2.5.4 / 2.4.6, `scipy` 1.18.1 / 1.17.1, `joblib` 1.6.0, `threadpoolctl`
  3.7.0, `narwhals` 2.28.0, `cloudpickle` 3.1.2.
- `uv sync --all-groups` → installed the eight packages above from wheels.
- `uv lock --check` → passed.
- `uv run pytest tests/unit/test_ml_dependency_boundary.py` → 11 passed.
- `uv run ruff check .` → all checks passed; `ruff format --check` on the new
  test → already formatted.
- `uv run mypy src/nba_data` → no issues in 98 source files.
- `uv run pytest` → 1532 passed, 257 skipped (the PostgreSQL integration lane,
  gated on `NBA_DATA_TEST_DATABASE`), 7 warnings (existing FastAPI and peewee
  deprecations).
- `uv run python scripts/validate_tasks.py` and `--all-worktrees` → passed.

Repeated on Python 3.12.11 (CI's minor version) in a disposable environment
(`UV_PROJECT_ENVIRONMENT` in the session scratchpad, `.venv` untouched):
`uv sync --all-groups --locked --python 3.12` installed `scikit-learn` 1.9.1,
`numpy` 2.5.4, `scipy` 1.18.1 from wheels; `uv run pytest` → 1532 passed,
257 skipped; the boundary test → 11 passed, including the smoke fit.

### Review findings addressed (2026-10-30)

1. *Medium: indirect lazy imports escaped both checks.* The static test now
   walks, breadth first, every local module the API and query modules can
   import, lazily or not, plus each package initializer an import runs, and
   reports each violation as a chain (`app -> helper -> sklearn`). Today that
   graph is 44 modules and it is clean. A regression test builds that exact
   scenario in `tmp_path`: an API module calls a helper outside the guarded
   trees whose function imports scikit-learn, and the helper's package
   `__init__` imports numpy. The runtime test now also runs the lifespan and
   serves `GET /api/v1/health`, with `DATABASE_URL` pointed at an unreachable
   address so `.env` can never route it to a real database.
2. *Medium: nothing exercised the dependency.* A new test fits
   `make_pipeline(StandardScaler(), LogisticRegression())`,
   `HistGradientBoostingClassifier`, and sigmoid `CalibratedClassifierCV` in a
   fresh interpreter. It uses seeded, separable data, runs `calibration_curve`,
   and asserts each model's probabilities, log loss < ln 2, Brier < 0.25, and
   AUC > 0.8. About 1.2 s.
3. *Low: no subprocess timeout.* Both subprocesses run under a 60-second
   timeout.

Mutation checks, each restored byte for byte from a copy afterwards:
- `import numpy` appended to `src/nba_data/db/repositories/queries/teams.py`,
  and a function-level `from nba_data import ml` in
  `src/nba_data/api/services/seasons.py` → static and runtime tests failed.
- The reviewer's scenario: a function-level
  `from sklearn.linear_model import LogisticRegression` inside
  `nba_data.db.session.create_db_engine()` → static and runtime tests failed.
- `import numpy` in the `src/nba_data/db/__init__.py` package initializer →
  static and runtime tests failed.

## Manual happy path

1. `uv sync --all-groups`, then
   `uv run python -c "import sklearn, numpy, scipy; print(sklearn.__version__)"`.
2. `uv lock --check`.
3. `uv run pytest tests/unit/test_ml_dependency_boundary.py -v`.

Expected result: step 1 prints `1.9.1`; step 2 reports the lock is up to date;
step 3 shows 11 passed, including
`test_nothing_the_api_can_import_imports_the_ml_stack`,
`test_starting_the_api_and_serving_a_request_loads_no_ml_module`, and
`test_the_installed_scikit_learn_fits_and_predicts_with_the_planned_estimators`.

## Manual sad path

1. Append `import numpy` to `src/nba_data/db/repositories/queries/teams.py` and
   run the boundary test. Remove it.
2. Add `def _probe() -> None:` with the body `from nba_data import ml` to the
   end of any module under `src/nba_data/api/services/`, and run the boundary
   test. Remove it.
3. Add `from sklearn.linear_model import LogisticRegression` as the first line
   of `create_db_engine()` in `src/nba_data/db/session.py`, and run the
   boundary test. Remove it.
4. Change `scikit-learn>=1.5` to `scikit-learn>=1.6` in `pyproject.toml`
   without relocking, run `uv lock --check`, then undo the edit.

Expected result:
- Step 1 fails both the static and the runtime test, naming the `teams` query
  module and `numpy`.
- Step 2 fails only the static test: the import is lazy and never runs, yet the
  walk still finds it.
- Step 3 fails both tests. The static failure prints the chain to
  `nba_data.db.session -> sklearn.linear_model`, and the runtime test catches
  it because the lifespan calls `create_db_engine()`.
- Step 4 fails because the lock no longer matches `pyproject.toml`.

Every check passes again once each edit is undone.

## Known limitations

- The card's evidence said scikit-learn brings `numpy`, `scipy`, `joblib`, and
  `threadpoolctl`. As resolved it also brings `narwhals` (a direct dependency
  of scikit-learn 1.9) and `cloudpickle` (through joblib 1.6). Both are pure
  Python and transitive; scikit-learn is still the only direct addition.
  Recorded in `PREDICTOR_PLAN.md` §6.
- The lock forks by interpreter: Python 3.11 gets `numpy` 2.4.6 and `scipy`
  1.17.1, 3.12+ gets 2.5.4 and 1.18.1. The 3.11 branch was not exercised;
  `requires-python` still allows it, though neither CI nor the owner uses it.
- Python 3.12 was run on Windows; CI's Linux 3.12 run is the first on that
  platform. The lock holds cp312 `manylinux_2_28_x86_64` wheels for all three
  numerical packages.
- The static walk sees `import` statements only. An import through
  `importlib.import_module` or `__import__` with a computed name is caught only
  if it runs while the app starts or serves `/api/v1/health`. The only such
  calls in `src/nba_data` today are the lazy attribute loader in
  `nba_data/validation/__init__.py`, which lies outside the 44 modules the API
  can reach.
- The walk is deliberately strict: an ML import under `if TYPE_CHECKING:` in
  any module the API can reach also fails it.
- `uv lock` and the 3.12 sync downloaded packages from PyPI, the dependency path
  the card names; nothing contacted Basketball Reference or a database.
