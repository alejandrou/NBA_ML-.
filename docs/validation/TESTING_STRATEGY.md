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
upgrade head`, verifies migration drift with `uv run alembic check`, and then
runs `uv run pytest tests/integration/test_team_season_loader_postgres.py`
and `uv run pytest tests/integration/test_api_postgres.py`. The job sets
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
afterward.

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
