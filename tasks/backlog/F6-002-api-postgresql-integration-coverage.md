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
rows.

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

- None.

# Review evidence

## Automated validation

- Command:
- Result:

## Manual happy path

1. Start the disposable PostgreSQL service and apply migrations.
2. Run `uv run pytest tests/integration/test_api_postgres.py`.
3. Inspect the teams and seasons responses returned by the real app.

Expected result: the integration test passes against PostgreSQL and leaves no
test rows after cleanup.

## Manual sad path

1. Run the test with PostgreSQL stopped or with migrations not applied.
2. Observe the integration lane result.

Expected result: the configured integration lane fails clearly; a local run may
skip with an explicit unavailable-database reason.

## Known limitations

- This is a focused route check, not a load or concurrency test and not a
  substitute for the offline unit suite.
