# Phase 4 - SQLAlchemy Migration

Status: proposed
Phase ID: `phase-4-sqlalchemy-migration`

## Goal

Move durable storage for selected core NBA entities toward SQLAlchemy and
Alembic while keeping legacy Peewee code available until replacement is
explicitly approved.

## Allowed Work

- Design and implement reviewed SQLAlchemy models and Alembic migrations.
- Add idempotent loader strategies for stable parser outputs.
- Add database tests that do not require live scraping.
- Document Peewee coexistence and migration boundaries.

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

## Default Validations

- `uv run ruff check .`
- `uv run pytest`
- `uv run alembic check`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Proceed to `phase-5-api` after stable core data can be loaded and queried.
