# Current Phase

Phase ID: `phase-4c-offline-cached-html-processing-and-load`
Status: `in_progress`

## Phase 4C - Offline Cached HTML Processing and Load

## Goal

Activate the offline path that consumes already-cached Basketball Reference
team-season HTML and prepares validated normalized rows before any later
database load.

The Phase 4C flow is:

`.html.gz -> parse -> normalize -> validate -> idempotent loader -> database`

`F4C-001` covers only the processor boundary through validation. It must not
write database rows.

## Transition State

- Phase 4B is closed after `F4B-001`, `F4B-002`, `F4B-003`, and
  `F4B-LIVE-001` were reviewed and marked `done`.
- The owner-approved Phase 4B pilot acquired only the approved BOS 2024 and DEN
  2023 team-season pages through the controlled manifest path.
- Phase 4 SQLAlchemy migration is closed and merged through PR #6.
- `F4-001`, `F4-002`, and `F4-003` are all `done`.
- The owner approved transitioning the roadmap to Phase 4C and preparing
  `F4C-001` as the first Phase 4C task.
- The owner approved implementing `F4C-001`.
- `F4C-001` is reviewed and marked `done`.
- No task is currently `approved`, `in_progress`, or `needs_review`.
- `F4C-002` and `F4C-003` remain `pending`.

## Current Guardrails

- Do not run live scraping or contact Basketball Reference.
- Do not refresh cache misses.
- Do not write DB loader data from cached HTML in `F4C-001`.
- Do not delete raw HTML, database records, volumes, Peewee code, or legacy
  code.
- Do not implement or run destructive migrations.
- Do not implement API, frontend, generated metrics, OVR, ranking, similarity,
  or ML work.
- Do not create another branch, commit, push, or open a PR without explicit
  owner approval.

## Next Safe Action

Wait for explicit owner approval before starting `F4C-002`. Do not connect
database loaders or write loader data from cached HTML until that approval is
given.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4c-offline-cached-html-processing-and-load.md`
- `specs/features/F4C-001-offline-cached-html-processor.md`
- `specs/phases/phase-4-sqlalchemy-migration.md`
- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`
- `tasks/feature-list.json`
