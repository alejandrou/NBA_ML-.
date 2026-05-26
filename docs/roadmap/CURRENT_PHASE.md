# Current Phase

Phase ID: `phase-4-sqlalchemy-migration`
Status: `proposed`

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
- No task is currently `approved`, `in_progress`, or `needs_review`.
- `F4-001` is `ready` as the next candidate task, not approved.
- `F4-002` and `F4-003` remain `pending`.
- Phase 4C offline cached HTML processing and loading remains future work.

## Current Guardrails

- Do not implement or run destructive migrations.
- Do not delete database data, raw HTML, Peewee code, or legacy scraper code.
- Do not run live scraping, contact Basketball Reference, or execute another
  raw HTML backfill pilot without exact owner approval.
- Do not write DB loader data until the selected schema and idempotent loader
  boundaries are approved.
- Do not implement API/frontend/OVR/ranking/similarity/ML work in this phase.

## Next Safe Action

Ask for explicit owner approval before promoting `F4-001` from `ready` to
`approved`. The first implementation step should define the exact reviewable
SQLAlchemy/Alembic scope for core team, player, and season entities while
preserving Peewee coexistence.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4-sqlalchemy-migration.md`
- `specs/phases/phase-4b-controlled-raw-html-backfill.md`
- `docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`
- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`
- `docs/migration/PEEWEE_TO_SQLALCHEMY.md`
- `tasks/feature-list.json`
