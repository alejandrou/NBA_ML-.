# F4-003 - Database Integration Validation Path

## Goal

Define a repeatable local PostgreSQL validation path for Phase 4 migration work
without running live scraping, deleting data, or implementing loaders.

## Requirements

- Add a harness command for local database validation.
- Make local PostgreSQL setup explicit through Docker Compose.
- Run Alembic upgrade and drift checks against the local database.
- Resolve the known raw nullable drift by aligning SQLAlchemy metadata with the
  existing `0001_initial_raw_core` migration.
- Keep validation independent from Basketball Reference, raw HTML acquisition,
  loaders, API/frontend, and generated metrics.

## Acceptance Criteria

- `scripts/harness/db-validate.sh` starts or checks local PostgreSQL and runs
  `uv run alembic upgrade head` followed by `uv run alembic check`.
- Raw timestamp SQLAlchemy metadata matches the existing nullable database
  schema for `fetched_at`, `requested_at`, and `started_at`.
- `uv run alembic check` passes cleanly after applying migrations to local
  PostgreSQL.
- Unit tests cover the nullable timestamp metadata alignment without requiring
  a database or network.
- Peewee, legacy scraper code, loaders, and Phase 4C remain untouched.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference requests.
- Data deletion, DB reset, or destructive migration.
- F4-002 loader repositories.
- Phase 4C offline cached HTML processing or loading.
- API, frontend, OVR, ranking, similarity, or ML work.
