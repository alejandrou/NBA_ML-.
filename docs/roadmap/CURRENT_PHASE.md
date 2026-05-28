# Current Phase

Phase ID: `phase-4d-full-offline-database-preparation`
Status: `approved`

## Phase 4D - Full Offline Database Preparation / Backfill Readiness

## Goal

Prepare the real local PostgreSQL database from all currently available cached
Basketball Reference `.html.gz` files so future read-only API endpoints can be
developed against real loaded data instead of mock data.

Full preparation means existing local cache only. Phase 4D must not live scrape,
refresh cache misses, contact Basketball Reference, or create new external raw
data.

## Transition State

- Phase 4C is closed after `F4C-001`, `F4C-002`, and `F4C-003` were reviewed
  and marked `done`.
- Phase 4C leaves behind the offline cached HTML processor, the idempotent
  loader bridge, and audit/quarantine reporting.
- Phase 4D is approved as the pre-API database preparation phase.
- `F4D-001` is `ready` as the first task.
- `F4D-002`, `F4D-003`, and `F4D-004` remain `pending`.
- No Phase 4D implementation has started.

## Phase Tasks

- `F4D-001`: Cached HTML inventory.
- `F4D-002`: Full offline backfill command.
- `F4D-003`: Data quality validation checks.
- `F4D-004`: API-ready database readiness documentation.

## Current Guardrails

- Use only existing cached `.html.gz` files.
- Do not run live scraping or contact Basketball Reference.
- Do not refresh cache misses.
- Do not delete raw HTML, database records, Docker/PostgreSQL volumes, Peewee
  code, or legacy code.
- Do not run destructive migrations.
- Do not implement API endpoints, frontend pages, generated metrics, OVR,
  ranking, similarity, recommendations, or ML work.
- Do not create a branch, commit, push, or open a PR without explicit owner
  approval.

## Next Safe Action

Implement `F4D-001` only after explicit owner approval. The first task should
inventory existing cached `.html.gz` files without database writes, live
scraping, cache refresh, or Basketball Reference contact.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4d-full-offline-database-preparation.md`
- `specs/features/F4D-001-cached-html-inventory.md`
- `specs/features/F4D-002-full-offline-backfill-command.md`
- `specs/features/F4D-003-data-quality-validation-checks.md`
- `specs/features/F4D-004-api-ready-database-readiness-documentation.md`
- `specs/phases/phase-4c-offline-cached-html-processing-and-load.md`
- `tasks/feature-list.json`
