# Current Phase

Phase ID: `phase-2-scraper-cache-integration`
Status: `in_progress`

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
- `F2-LIVE-001` is complete and awaiting review.
- No Phase 2 task is currently `approved` or `in_progress`.
- `F2-005`, `F2-006`, and later Phase 2 tasks remain `pending` until explicit
  owner approval.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-2-scraper-cache-integration.md`
- `tasks/feature-list.json`
