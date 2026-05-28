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

`F4C-002` connects validated processor output to the reviewed idempotent core
loaders. It does not add reporting/quarantine workflow.

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
- The owner approved implementing `F4C-002`.
- `F4C-002` is reviewed and marked `done`.
- The owner approved implementing `F4C-003` after startup inspection confirmed
  source-of-truth consistency.
- `F4C-003` is implemented and awaits review.

## Current Guardrails

- Do not run live scraping or contact Basketball Reference.
- Do not refresh cache misses.
- Do not run another offline DB load workflow until the owner explicitly
  approves the next task or operation.
- Do not delete raw HTML, database records, volumes, Peewee code, or legacy
  code.
- Do not implement or run destructive migrations.
- Do not implement API, frontend, generated metrics, OVR, ranking, similarity,
  or ML work.
- Do not create another branch, commit, push, or open a PR without explicit
  owner approval.

## Next Safe Action

Review `F4C-003` against its feature spec and close it as `done` only after
approval and validation, or request the smallest corrective change.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4c-offline-cached-html-processing-and-load.md`
- `specs/features/F4C-001-offline-cached-html-processor.md`
- `specs/features/F4C-002-connect-offline-processor-to-idempotent-loaders.md`
- `specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md`
- `specs/phases/phase-4-sqlalchemy-migration.md`
- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`
- `tasks/feature-list.json`
