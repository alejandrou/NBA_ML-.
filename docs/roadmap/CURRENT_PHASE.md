# Current Phase

Phase ID: `phase-4c-offline-cached-html-processing-and-load`
Status: `done`

## Phase 4C - Offline Cached HTML Processing and Load

## Goal

Activate the offline path that consumes already-cached Basketball Reference
team-season HTML and prepares validated normalized rows before any later
database load.

The Phase 4C flow is:

`.html.gz -> parse -> normalize -> validate -> idempotent loader -> database`

## Closure State

- Phase 4B is closed after `F4B-001`, `F4B-002`, `F4B-003`, and
  `F4B-LIVE-001` were reviewed and marked `done`.
- The owner-approved Phase 4B pilot acquired only the approved BOS 2024 and DEN
  2023 team-season pages through the controlled manifest path.
- Phase 4 SQLAlchemy migration is closed and merged through PR #6.
- `F4-001`, `F4-002`, and `F4-003` are all `done`.
- `F4C-001` is reviewed and marked `done`.
- `F4C-002` is reviewed and marked `done`.
- `F4C-003` is reviewed and marked `done`.
- Phase 4C is closed after review and validation.

## Closure Summary

- `F4C-001` added the offline cached HTML processor boundary through parse,
  normalize, and validate without accepting a network client or writing DB
  rows.
- `F4C-002` connected validated processor entries to the reviewed idempotent
  core loader path with entry-level savepoints and caller-owned commits.
- `F4C-003` added audit/quarantine reporting that distinguishes parsed,
  validated, loaded, skipped, and quarantined rows, with source context and
  retry hints.

## Remaining Risk

- Phase 4C proves the platform path with report-level lineage only; it does not
  add persisted source lineage columns, stats tables, broad historical loads,
  API endpoints, frontend pages, generated metrics, OVR, rankings, similarity,
  or ML.
- Any future pilot operation, Phase 5 transition, branch, commit, push, PR,
  live scraping, Basketball Reference contact, cache refresh, schema change,
  destructive DB change, or data deletion still requires explicit owner
  approval.

## Next Safe Action

Prepare a Phase 5 transition proposal only after explicit owner approval. Do
not start API/frontend/OVR/ranking/similarity/ML work automatically.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4c-offline-cached-html-processing-and-load.md`
- `specs/features/F4C-001-offline-cached-html-processor.md`
- `specs/features/F4C-002-connect-offline-processor-to-idempotent-loaders.md`
- `specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md`
- `specs/phases/phase-4-sqlalchemy-migration.md`
- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`
- `tasks/feature-list.json`
