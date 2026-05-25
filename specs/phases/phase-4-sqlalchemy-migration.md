# Phase 4 - SQLAlchemy Migration

Status: proposed
Phase ID: `phase-4-sqlalchemy-migration`

## Goal

Move durable storage for selected core NBA entities toward SQLAlchemy and
Alembic while keeping legacy Peewee code available until replacement is
explicitly approved.

Phase 4 runs after Phase 4B has established controlled raw HTML acquisition and
before Phase 4C performs offline cached HTML processing and loading.

## Allowed Work

- Design and implement reviewed SQLAlchemy models and Alembic migrations.
- Add idempotent loader strategies for stable parser outputs.
- Add database tests that do not require live scraping.
- Document Peewee coexistence and migration boundaries.
- Prepare loaders for validated normalized rows produced by later offline
  processing; do not load directly from raw HTML.

## Forbidden Without Owner Approval

- Deleting Peewee code.
- Deleting legacy scraper code.
- Migrating the whole database in one step.
- Deleting local or production data.
- API implementation.
- Frontend implementation.
- OVR, ranking, similarity, or ML feature implementation.

## Sensitive Gates

- Destructive migrations.
- Data deletion.
- Broad schema rewrites.
- Loader behavior that cannot be rerun idempotently.

## Initial Ready Tasks

None while this phase is proposed. Candidate tasks remain `pending` until this
phase becomes current.

## Done Criteria

- Selected core tables are modeled with SQLAlchemy.
- Alembic migrations are reviewable and reversible where practical.
- Idempotent loading is tested.
- Peewee coexistence boundaries are documented.
- Loader boundaries expect validated normalized rows, not raw HTML.

## Default Validations

- `uv run ruff check .`
- `uv run pytest`
- `uv run alembic check`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Proceed to `phase-4c-offline-cached-html-processing-and-load` after stable
schema, idempotent loaders, and local DB validation are available. Proceed to
`phase-5-api` only after selected core data can be loaded and queried.
