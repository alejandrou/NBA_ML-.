# Current Phase

Phase ID: `phase-4-sqlalchemy-migration`
Status: `done`

## Phase 4 - SQLAlchemy Migration

## Goal

Prepare reviewed SQLAlchemy and Alembic migration work for selected core NBA
entities while preserving Peewee and legacy scraper coexistence.

Phase 4 follows the completed Phase 4B controlled raw HTML acquisition work and
must finish before Phase 4C attempts offline cached HTML processing and loading
through idempotent repositories.

## Transition State

- Phase 4B is closed after `F4B-001`, `F4B-002`, `F4B-003`, and
  `F4B-LIVE-001` were reviewed and marked `done`.
- The owner-approved Phase 4B pilot acquired only the approved BOS 2024 and DEN
  2023 team-season pages through the controlled manifest path.
- `F4-001` was reviewed and marked `done`.
- `F4-003` was reviewed and marked `done`.
- `F4-002` was reviewed and marked `done`.
- `F4-001`, `F4-002`, and `F4-003` are all `done`.
- No task is currently `approved`, `in_progress`, or `needs_review`.
- Phase 4 is closed.
- Phase 4C offline cached HTML processing and loading remains future work and
  is not approved.

## Current Guardrails

- Do not implement or run destructive migrations.
- Do not delete database data, raw HTML, Peewee code, or legacy scraper code.
- Do not run live scraping, contact Basketball Reference, or execute another
  raw HTML backfill pilot without exact owner approval.
- Do not start Phase 4C, cached HTML processing, API/frontend, generated
  metrics, OVR, ranking, similarity, or ML work without explicit owner
  approval.

## Next Safe Action

Prepare commit, push, and PR only after explicit owner approval. Phase 4C
remains pending until the owner approves the phase transition and first task.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4-sqlalchemy-migration.md`
- `specs/phases/phase-4b-controlled-raw-html-backfill.md`
- `docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`
- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`
- `docs/migration/PEEWEE_TO_SQLALCHEMY.md`
- `tasks/feature-list.json`
