# F4D-004 - API-Ready Database Readiness Documentation

## Goal

Document the final local workflow that future API work can rely on after Phase
4D is reviewed and approved.

The documentation should let the owner prepare a local PostgreSQL database with
real cached data and verify that it is useful for API development.

## Documentation Requirements

- Explain how to start local PostgreSQL.
- Explain how to run Alembic migrations.
- Explain how to run the cache inventory.
- Explain how to run the full offline backfill.
- Explain how to run data quality checks.
- State what data is expected to exist after a successful run.
- Include example SQL queries that prove the database contains useful data for
  future API development.
- Clearly state that API work starts only after Phase 4D is reviewed and
  approved.

## Technical Requirements

- Reference only existing Phase 4D commands or functions after they are
  implemented.
- Keep the workflow offline-only and cache-only.
- Do not document live scraping, cache refresh, destructive migrations, data
  deletion, API implementation, frontend implementation, or generated metrics
  work as part of Phase 4D.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4D-004-api-ready-database-readiness-documentation.md`.
- Docs explain how to start local PostgreSQL.
- Docs explain how to run Alembic migrations.
- Docs explain how to run cache inventory, full offline backfill, and data
  quality checks.
- Docs state what data is expected after a successful run.
- Docs include example SQL queries that prove useful data exists for future API
  development.
- Docs clearly state API work starts only after Phase 4D is reviewed and
  approved.
- No API, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML implementation is introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh or cache-miss acquisition.
- Deleting raw HTML, database records, local databases, or PostgreSQL volumes.
- Destructive migrations.
- API or frontend implementation.
- Generated metrics, OVR, ranking, similarity, recommendations, or ML work.
