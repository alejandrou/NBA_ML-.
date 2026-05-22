# Current Phase

Phase ID: `phase-4a-legacy-scraper-consolidation`
Status: `in_progress`

## Phase 4A - Legacy Scraper Consolidation

## Goal

Prepare legacy Basketball Reference scraper paths for future controlled raw
HTML backfill by consolidating team-season page acquisition behind the central
cache-first provider.

The target pipeline remains:

`one team-season URL -> HtmlCache/BasketballReferenceClient -> one raw HTML file -> multiple table parsers`

## Completed Work

- `F4A-000` is complete. It defines the offline legacy-vs-new parser parity
  strategy and the gated one-page manual live acquisition smoke-test strategy.
- The validation strategy uses frozen HTML fixtures or approved cached HTML
  copied into test fixtures for unit tests and CI.
- The manual smoke-test strategy is cache-first, owner-approved per exact URL,
  limited to at most one live request on cache miss, and shape-only.
- `F4A-002` is complete. It creates the bounded offline cached HTML processing
  design before any runtime offline processor, controlled backfill, or Phase 4
  loader work.
- `F4A-001` is complete. Legacy player/team-season and included team scrapers
  now route normal acquisition through cache-first providers and offline tests.

## Current Guardrails

- Phase 4 SQLAlchemy migration remains inactive; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.
- Do not run live scraping or contact Basketball Reference without explicit
  owner approval for the exact URL.
- Do not run controlled raw HTML backfill.
- Do not write database data, apply migrations, delete legacy/Peewee code, or
  implement API/frontend/OVR work.

## Next Safe Action

Prepare a Phase 4A closure or transition summary before changing phases. Ask
the owner for explicit approval before activating Phase 4 SQLAlchemy migration
or running any live/backfill work.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4a-legacy-scraper-consolidation.md`
- `specs/features/F4A-000-legacy-parity-and-acquisition-smoke-test-strategy.md`
- `specs/features/F4A-002-bounded-offline-cached-html-processing.md`
- `docs/decisions/0016-live-vs-offline-validation.md`
- `tasks/feature-list.json`
