---
id: F6-006
title: Run the whole integration lane in CI instead of three named files
areas:
  - testing
priority: 85
depends_on: []
read:
  - .github/workflows/ci.yml
  - tests/integration/test_api_unreachable_database.py
validation:
  - uv run pytest tests/integration
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make the PostgreSQL CI job run every test in `tests/integration/`, so a new
integration test cannot be written and then silently never run. One such test
exists today.

# Evidence and current state

`.github/workflows/ci.yml` has two jobs, and between them they do not run one of
the four integration modules:

- The `test` job runs `uv run pytest -m "not integration and not live"`. Every
  module in `tests/integration/` carries `@pytest.mark.integration`, so all four
  are excluded there. Verified: `tests/integration/test_api_postgres.py:78`,
  `test_api_unreachable_database.py:27`,
  `test_synthetic_team_code_constraints_postgres.py:85`, and
  `test_team_season_loader_postgres.py:27`.
- The `postgres-integration` job ends with three steps that each name one file:
  "Run PostgreSQL loader integration test", "Run PostgreSQL API integration
  test", and "Run PostgreSQL check-constraint integration test".

`tests/integration/test_api_unreachable_database.py` is in neither list. It is
the test asserting that `GET /api/v1/health/ready` answers 503 within a bound
instead of hanging when the database address is blackholed — the guarantee
`F6-003` specified and `F6-005` implemented. **It has never run in CI.**

It runs and passes locally: `uv run pytest tests/integration` selects all four,
runs this one, and skips the other three with the
`NBA_DATA_REQUIRE_POSTGRES_INTEGRATION` guard
(`tests/integration/test_api_postgres.py:36`).

The enumeration is the defect, not the omission. Three named steps must be
edited by hand every time a module is added, and nothing fails when they are not.

# Human decisions or resources

- None.

# Acceptance criteria

- The `postgres-integration` job runs the integration lane as a directory —
  `uv run pytest tests/integration` — rather than naming individual files. The
  three per-file steps are replaced, not supplemented.
- `tests/integration/test_api_unreachable_database.py` runs in CI as part of that
  step, and the CI log for the branch shows it passing.
- The `NBA_DATA_REQUIRE_POSTGRES_INTEGRATION` environment variable stays set on
  the job, so the three PostgreSQL modules still run rather than skipping.
- The offline `test` job is unchanged and still excludes `integration` and `live`.
- Adding a new file under `tests/integration/` requires no workflow edit for it
  to run. State this in the workflow as a short comment on the step, so the next
  reader does not reintroduce the enumeration.
- The `alembic upgrade`, `alembic check`, and downgrade round-trip steps are
  untouched and still run before the tests.

# Scope

`.github/workflows/ci.yml` only.

# Out of scope

Changing any test, marker, or skip guard. Adding coverage measurement. Adding a
mypy step — `F6-007` owns that. Changing the offline job's selection expression.
Speeding up or reordering the jobs.

# Impact

CI only; no source or test behavior changes. The `postgres-integration` job gains
one test and takes a few seconds longer. A previously unverified readiness
guarantee starts being verified on every push, so it may fail on a runner whose
network handles the blackhole address differently than a local machine — the test
docstring at `tests/integration/test_api_unreachable_database.py:1-8` explains
why both a timeout and an outright rejection satisfy it.

# Implementation notes

Run `uv run pytest tests/integration` locally first and record what it selects,
runs, and skips. Locally the three PostgreSQL modules skip unless the guard
variable is exported, which is the expected local result and is not a failure.

Do not add `-m integration` on top of the directory path. The directory is the
lane; the marker is what keeps these tests out of the offline job. Keeping both
in sync is the same maintenance trap as the file list.

# Durable knowledge updates

- `docs/validation/TESTING_STRATEGY.md` — if it describes the CI lanes by naming
  the individual integration modules, correct it to describe the directory.

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
