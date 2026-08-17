# Testing Strategy

## Offline suite

The unit-test lane is deliberately independent of PostgreSQL and network
access. It runs Ruff and:

```bash
uv run pytest -m "not integration and not live"
```

The full local `uv run pytest` command may still collect the PostgreSQL
integration test. Developers without a running database receive the existing
skip, and no live scraping or Basketball Reference request is made.

## Required PostgreSQL integration lane

CI runs a separate `postgres-integration` job against an ephemeral PostgreSQL
16 service with:

```text
DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba
```

The job waits for a successful database connection, runs `uv run alembic
upgrade head`, verifies migration drift with `uv run alembic check`, then
round-trips the newest revision (`downgrade -1`, `upgrade head`, `check`) so a
revision that cannot be undone fails the build, and then runs
`uv run pytest tests/integration` so every integration module runs. The job sets
`NBA_DATA_REQUIRE_POSTGRES_INTEGRATION=1`; with that flag, a connection
failure, missing migration table, or incompatible revision fails the test
instead of being reported as a skip. Local runs without the flag retain the
skip path for developers who have not started PostgreSQL.

`test_api_postgres.py` additionally requires `core.teams`/`core.seasons` to be
empty before and after it runs, and fails (rather than skipping) if it finds
existing rows, so it must never be pointed at a populated database.
`scripts/validate_database.sh` only exercises the loader test against the
developer's regular local database. To run `test_api_postgres.py` locally
without risking real data, use `uv run python
scripts/validate_postgres_local.py`, which migrates and tests a disposable,
uniquely named database on the same PostgreSQL server and always drops it
afterward. That script mirrors the CI job, round trip included, and is the way
to validate a new migration locally — never `alembic upgrade head` against the
developer's real database, which is an owner-approved operation.

`test_synthetic_team_code_constraints_postgres.py` exercises the four
`ck_core_*_not_synthetic` check constraints on PostgreSQL itself, because the
conditions are generated SQL and the unit tests only prove them against SQLite.
It rolls back every insert, and it skips on a database below the migration head
— the constraints do not exist there — which the require-flag turns into a
failure in CI.

## Test rules

- Unit tests for settings defaults.
- Unit tests for HTML cache `.html.gz` read/write behavior.
- Unit tests for the rate-limited client with mocked HTTP.
- Unit tests for parser behavior with fixture HTML.

- No network calls in tests.
- No live scraping in CI.
- No Basketball Reference contact in CI.
- Use fixture HTML for parser tests.
- Use mocks for HTTP client tests.
- Use temporary directories for cache tests.

## Future tests

- DB integration tests for SQLAlchemy models and repositories.
- Data quality tests for row counts, nullability, duplicate natural keys, and
  numeric ranges.
- Manual live smoke tests for approved scraping jobs only.
