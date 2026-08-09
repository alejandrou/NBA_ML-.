---
id: F6-002
title: Exercise the read-only API against PostgreSQL
areas:
  - api
  - database-read
  - testing
priority: 80
depends_on:
  - F6-001
read:
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - src/nba_data/api/app.py
  - src/nba_data/db/repositories/queries/teams.py
  - src/nba_data/db/repositories/queries/seasons.py
  - tests/unit/test_team_api.py
  - tests/unit/test_season_api.py
validation:
  - uv run pytest tests/integration/test_api_postgres.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Add a small, isolated PostgreSQL integration test for the shipped read-only
teams and seasons API routes, using the real app lifespan, query repositories,
services, schemas, and migrated database.

# Evidence and current state

- `src/nba_data/api/` currently exposes health, teams, and seasons, but all HTTP
  coverage is under `tests/unit/` and uses dependency overrides or in-memory
  SQLite.
- `tests/unit/test_team_api.py` and `tests/unit/test_season_api.py` prove the
  HTTP contracts and vertical slices against SQLite, but cannot catch
  PostgreSQL-specific SQL, migration drift, or differences in the real
  application session lifecycle.
- `docs/architecture/API_ARCHITECTURE.md` explicitly says real database
  integration is a future, separate layer. F6-001 supplies the PostgreSQL CI
  lane this test can run in.

# Human decisions or resources

- None.

# Acceptance criteria

- `tests/integration/test_api_postgres.py` is marked `integration` and uses the
  configured PostgreSQL database after migrations, without network access.
- The test seeds minimal teams and NBA/non-NBA seasons through SQLAlchemy,
  exercises the real FastAPI app with `TestClient`, and rolls its data back or
  otherwise leaves no durable test rows behind.
- The test covers the real teams and seasons list paths, including deterministic
  response shape/order and filtered totals, plus a missing-resource 404 for at
  least one single-resource route.
- The test runs in the F6-001 database CI lane and remains skipped only when a
  developer runs it locally without the configured PostgreSQL service.
- No write-capable repository or scraping module is imported by the API path.

# Scope

`tests/integration/test_api_postgres.py`, the CI invocation needed to run it,
and any narrowly scoped test fixture/helper required to isolate PostgreSQL
rows. Extended during hardening to add: an explicit pre/post-seed row-count
guard in the test itself, a dynamic Alembic head comparison (replacing a
static revision check), `scripts/validate_postgres_local.py` for exercising
the success path against a disposable local database, and a bounded connect
timeout for the pre-existing loader integration test (previously unbounded,
which hung the full local `pytest` run when PostgreSQL was unreachable).

# Out of scope

New API routes, changes to the public response contract, schema or migration
changes, frontend work, live scraping, and replacing the existing offline HTTP
tests.

# Impact

Adds dialect and migration coverage for the existing API without changing its
HTTP surface. It exercises the app-owned Engine/sessionmaker and request-scoped
Session against the real `core` tables.

# Implementation notes

- Follow the synchronous SQLAlchemy and `TestClient` model already documented
  for the API; do not add an async database stack.
- Use unique test values and a transaction/cleanup strategy that is safe when
  the CI database is shared by the two integration tests in one job.
- Keep assertions at the public JSON boundary rather than exposing ORM objects.

# Durable knowledge updates

- `test_api_postgres.py` now fails (does not skip or seed) whenever
  `core.teams`/`core.seasons` already hold rows, so it is safe to point at a
  developer's real local database by accident. To exercise the pass path
  locally, run `uv run python scripts/validate_postgres_local.py`, which
  creates a uniquely named scratch database on the same PostgreSQL server,
  migrates and tests only that database, and always drops it afterward.

# Review evidence

## Automated validation

- Command: `uv run ruff check .`
- Result: All checks passed.
- Command: `uv run pytest -m "not integration and not live"`
- Result: 387 passed, 2 deselected, 7 warnings in 8.03s.
- Command: `uv run pytest tests/integration/test_api_postgres.py`, run against the
  developer's local Docker PostgreSQL (`nba` database, populated with 37 teams
  and 26 seasons)
- Result: 1 error in 0.68s — `_fail_unless_empty` correctly refused to run,
  reporting "PostgreSQL database is not isolated (before seeding): found 37
  team row(s) and 26 season row(s)"; no rows were seeded or mutated.
- Command: `uv run pytest -q` (full suite), same populated local PostgreSQL
- Result: 388 passed, 1 error in 9.87s. The loader integration test now
  completes immediately (bounded `connect_timeout`, no more indefinite hang);
  the single error is the same intentional isolation guard above — this is
  the expected/safe outcome of running the full suite locally against a
  populated database, not a regression.
- Command: `uv run python scripts/validate_postgres_local.py`
- Result: Passed end-to-end. Created `nba_test_tmp_8f1edc3ca36e4289` on the
  same PostgreSQL server, ran `alembic upgrade head`, `alembic check`, both
  PostgreSQL integration tests (both passed for real, not skipped), verified
  `core.teams`/`core.seasons` were empty after cleanup, then dropped the
  temporary database.
- Follow-up check: `docker exec nba_postgres psql -U nba -d nba -c "SELECT
  datname FROM pg_database WHERE datname LIKE 'nba_test_tmp_%';"` returned 0
  rows (temp database fully cleaned up), and `core.teams`/`core.seasons`
  counts in `nba` were still 37/26 — confirming the real local database was
  never touched.
- Command: `uv run python scripts/validate_tasks.py`
- Result: Task validation passed.
- Command: `$env:NBA_DATA_REQUIRE_POSTGRES_INTEGRATION = '1'; uv run pytest tests/integration/test_api_postgres.py`
- Result: Expected exit code 1 with a clear PostgreSQL-unavailable setup error, confirming the CI gate does not silently skip.

## Manual happy path

1. Start the disposable PostgreSQL service and apply migrations.
2. Run `uv run pytest tests/integration/test_api_postgres.py`.
3. Inspect the teams and seasons responses returned by the real app.

Expected result: the integration test passes against PostgreSQL, returns the
seeded teams in name order, returns only the seeded NBA seasons in year order,
returns 404 for the non-NBA season path, and leaves no test rows after cleanup.

## Manual sad path

1. Run the test with PostgreSQL stopped.
2. Run the test with PostgreSQL available but migrations not applied.
3. Observe the local result and the CI integration-lane result.

Expected result: a local run skips with an explicit unavailable-database
reason when the service is stopped; an unmigrated database fails clearly; the
configured CI integration lane fails instead of skipping.

## Known limitations

- This is a focused route check, not a load or concurrency test and not a
  substitute for the offline unit suite.
- Running `uv run pytest` (or the API test file directly) against a local
  PostgreSQL that already has data in `core.teams`/`core.seasons` — as a
  developer's real `nba` database typically will — fails by design rather
  than skipping. Use `uv run python scripts/validate_postgres_local.py` to
  exercise the pass path locally without touching that data.
- `scripts/validate_postgres_local.py` requires the configured PostgreSQL
  role to have `CREATEDB` privilege; it was not exercised against a role
  lacking that privilege.
