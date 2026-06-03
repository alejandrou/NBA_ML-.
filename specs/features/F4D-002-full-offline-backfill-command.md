# F4D-002 - Full Offline Backfill Command

## Goal

Create a repeatable offline command or script that loads all valid cached
inventory entries into local PostgreSQL using the Phase 4C offline processor
and existing idempotent loaders.

This task uses only already-cached `.html.gz` files. It must not scrape, refresh
cache misses, contact Basketball Reference, delete data, or perform destructive
migrations.

## Functional Requirements

- Read valid entries from the F4D-001 cache inventory.
- Process each valid inventory entry through the existing Phase 4C offline
  processor.
- Load only validated processor entries through the existing idempotent loaders.
- Skip or reject invalid processor results before any database write.
- Use entry-level transaction boundaries so one failed entry does not leave
  partial writes.
- Preserve caller-owned transaction behavior where existing loader contracts
  require it.
- Be idempotent: rerunning the same backfill must not duplicate core rows.
- Produce a load report using the existing reporting and quarantine model.
- Do not delete existing data.

## Technical Requirements

- Reuse the Phase 4C offline processor, offline loader bridge, and reporting
  model.
- Run Alembic migrations normally only as part of the local preparation
  workflow. Do not introduce destructive migrations.
- Do not accept or import network clients in the backfill path.
- Tests must cover idempotency, invalid-entry skip behavior, transaction
  rollback, no-network boundaries, and report generation.
- Tests must not run live scraping or contact Basketball Reference.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4D-002-full-offline-backfill-command.md`.
- Backfill runs only against existing cached files from the inventory.
- Backfill processes each valid inventory entry through the Phase 4C offline
  processor.
- Backfill loads only validated entries through existing idempotent loaders.
- Invalid processor results are skipped or rejected before DB writes.
- Entry-level transaction boundaries prevent one failed entry from leaving
  partial writes.
- Rerunning the same backfill does not duplicate core rows.
- Backfill produces a load report using the existing reporting and quarantine
  model.
- Backfill does not delete existing data, perform destructive migrations,
  scrape, refresh cache misses, or contact the network.

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
- Removing Peewee or legacy code.
- Persisted source lineage columns unless separately approved in a later phase.
- API, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML work.
