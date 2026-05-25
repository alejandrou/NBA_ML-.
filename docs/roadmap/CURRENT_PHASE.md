# Current Phase

Phase ID: `phase-4b-controlled-raw-html-backfill`
Status: `proposed`

## Phase 4B - Controlled Raw HTML Backfill

## Goal

Define and later implement a controlled raw HTML acquisition path before any
offline database loading.

The target acquisition pipeline is:

`approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`

Phase 4B is not a parser, loader, migration, or historical full scrape phase.
It exists so future raw HTML backfill is explicit, owner-approved,
cache-first, sequential, and auditable.

## Transition State

- `F4A-001` was confirmed `done` in `tasks/feature-list.json` before moving the
  current phase to Phase 4B.
- `F4B-001` is `done` after explicit owner approval for the design-only
  manifest task.
- `F4B-002` is `done` after review approval for the offline dry-run validation
  task.
- `F4B-003` is `done` after owner approval, review, and offline validation for
  the sequential cache-first acquisition runner implementation.
- `F4B-LIVE-001` is `needs_review` after the owner-approved two-URL live
  acquisition pilot.
- Phase 4 SQLAlchemy migration remains inactive; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.
- Phase 4C offline cached HTML processing and loading remains future work.

## Current Guardrails

- Do not approve or start `F4B-LIVE-001` while this phase is `proposed` unless
  the owner explicitly approves the exact manifest and task.
- Do not run live scraping, contact Basketball Reference, or execute a backfill
  pilot without owner approval for the exact manifest.
- Do not write database data, apply migrations, delete legacy/Peewee code,
  delete raw HTML, or implement API/frontend/OVR work.
- Live acquisition, when later approved, must remain sequential, cache-first,
  default to 10 requests/minute, and never exceed 20 requests/minute.
- The first real backfill pilot defaults to at most five team-season URLs.
- Player-specific pages are outside the initial pilot unless a later task and
  exact manifest explicitly approve them.

## Next Safe Action

Review the `F4B-LIVE-001` pilot result and either close the task as `done` or
request changes. Do not rerun the live acquisition or expand the manifest
without separate explicit owner approval.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4b-controlled-raw-html-backfill.md`
- `specs/features/F4B-001-controlled-raw-html-backfill-manifest.md`
- `specs/phases/phase-4c-offline-cached-html-processing-and-load.md`
- `specs/phases/phase-4-sqlalchemy-migration.md`
- `tasks/feature-list.json`
