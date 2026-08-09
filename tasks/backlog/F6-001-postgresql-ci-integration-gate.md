---
id: F6-001
title: Enforce PostgreSQL migrations and loader integration in CI
areas:
  - testing
  - documentation
priority: 70
depends_on:
  - F5-005
read:
  - .github/workflows/ci.yml
  - scripts/validate_database.sh
  - docker-compose.yml
  - tests/integration/test_team_season_loader_postgres.py
  - docs/validation/TESTING_STRATEGY.md
validation:
  - uv run python scripts/validate_tasks.py
  - uv run pytest tests/unit/test_validate_tasks.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make the existing PostgreSQL migration and team-season loader integration test
an enforced CI gate while keeping the ordinary unit-test job offline.

# Evidence and current state

- `.github/workflows/ci.yml` has one Python job that installs dependencies,
  runs Ruff, and runs `uv run pytest`; it does not provision PostgreSQL, apply
  Alembic migrations, or run a required database integration lane.
- `tests/integration/test_team_season_loader_postgres.py` is marked
  `integration`, but skips when PostgreSQL is unavailable or the schema is not
  migrated. The current CI job therefore cannot prove the loader works against
  the PostgreSQL dialect or the migrated schema.
- `scripts/validate_database.sh` already defines the local sequence of starting
  PostgreSQL, running `alembic upgrade head`, `alembic check`, and the loader
  integration test. The CI task should reuse those same boundaries rather than
  inventing a second validation contract.

# Human decisions or resources

- None.

# Acceptance criteria

- CI has a PostgreSQL 16 service or equivalent ephemeral database for a
  dedicated integration job/step, with `DATABASE_URL` matching the service.
- The integration lane waits for PostgreSQL readiness, runs
  `uv run alembic upgrade head`, then `uv run alembic check`, before running
  the PostgreSQL loader integration test.
- The integration lane cannot pass by silently skipping when its configured
  database is unavailable or at an incompatible migration revision; local
  runs without PostgreSQL may retain the existing skip behaviour.
- The existing unit-test lane remains runnable without PostgreSQL and without
  network access.
- `docs/validation/TESTING_STRATEGY.md` distinguishes the offline suite from
  the required PostgreSQL integration lane.

# Scope

`.github/workflows/ci.yml`, the PostgreSQL integration-test guard needed to make
CI failures visible, and `docs/validation/TESTING_STRATEGY.md`.

# Out of scope

Changing application or loader behaviour, adding schema objects, applying
migrations to shared databases, live scraping, and adding API endpoints.

# Impact

CI runtime and database validation only. The task makes the existing migration
chain and team-season loader integration test an enforceable check; it does not
change production tables or application contracts.

# Implementation notes

- Keep the unit job free of service dependencies so parser, API, and task tests
  stay fast and offline.
- Use an ephemeral CI database and explicit environment variables. Do not use
  repository secrets or a persistent external database.
- Preserve the local skip path for developers who have not started Docker, but
  make the CI-configured path fail loudly instead of reporting a false green.
- Do not run live acquisition or any Basketball Reference request.

# Durable knowledge updates

- `docs/validation/TESTING_STRATEGY.md` — record the separate offline and
  PostgreSQL CI validation lanes.

# Review evidence

## Automated validation

- Command:
- Result:

## Manual happy path

1. Open the CI run for a branch containing the workflow change.
2. Confirm the PostgreSQL service becomes ready and migrations reach head.
3. Confirm the loader integration test passes without a skip.

Expected result: the dedicated database lane is green and the unit lane remains
independent of PostgreSQL.

## Manual sad path

1. Temporarily point the integration lane at an unavailable database or remove
   the migration step in a local test branch.
2. Run the integration lane.
3. Inspect the result rather than relying on the unit job.

Expected result: the database lane fails with a connection or migration error;
it does not pass by skipping the integration test.

## Known limitations

- The gate validates the existing loader integration scenario, not the full
  production data volume or live acquisition path.
