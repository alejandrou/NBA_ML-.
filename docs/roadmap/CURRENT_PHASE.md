# Current Phase

Phase ID: `phase-2-scraper-cache-integration`
Status: `done`

## Phase 2 - Scraper Cache Integration

## Goal

Integrate the current scraping flow with `BasketballReferenceClient` and
`HtmlCache` without rewriting the whole scraper.

## Allowed Work

- Adapt fetch/cache boundaries for team-season pages.
- Add tests with mocks only.
- Add and use local HTML fixtures.
- Build parser flow from cached HTML.
- Update documentation and progress memory.
- Keep all validation offline.

## Forbidden Without Owner Approval

- Live scraping.
- Contacting Basketball Reference.
- Deleting Peewee or legacy scraper code.
- Migrating the whole database.
- API implementation.
- Frontend implementation.
- OVR, ranking, similarity, or ML feature implementation.
- Full SQLAlchemy loader migration.

## Current Backlog State

- `F2-001` is reviewed and done.
- `F2-002` is reviewed and done.
- `F2-003` is reviewed and done.
- `F2-004` is reviewed and done.
- `F2-LIVE-001` is reviewed and done.
- `F2-005` is reviewed and done.
- `F2-006` is reviewed and done.
- No Phase 2 task is currently `approved`, `in_progress`, or `needs_review`.
- Phase 3 is not active. Future phase tasks remain `pending` until an explicit
  owner-approved phase transition.

## Closure Notes

- Phase 2 closed after offline validation and conservative cleanup audit.
- Loader strategy and SQLAlchemy migration planning are documented under
  `docs/migration/`.
- No live scraping, Basketball Reference contact, DB writes, DB migrations,
  legacy/Peewee deletion, dependency removal, API/frontend/OVR work, branch, or
  PR action occurred during closure.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-2-scraper-cache-integration.md`
- `tasks/feature-list.json`
