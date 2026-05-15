# Tasks

## Done

- Phase 1 foundations are complete and reviewed.
- F1-001 through F1-011 are marked `done`.
- Global phase governance now defines rolling backlog behavior across phases.
- `F2-001`: Adapt team-season fetch/cache flow.
- `F2-002`: Create pure parser flow for cached team-season HTML.
- `F2-003`: Add realistic HTML fixtures without live scraping in tests.

## Current

- Current phase: `phase-2-scraper-cache-integration`.
- Current phase status: `in_progress`.
- No task is `approved` or `in_progress`.

## Needs Review

- `F2-004`: Adapt legacy team-season scraper entrypoint to use client/cache.

## Next

- Review `F2-004`. Do not start `F2-LIVE-001` or any other task without
  explicit approval.

## Later

- Phase 2 pending tasks: gated one-page live smoke test, loader strategy, and
  SQLAlchemy migration planning.
- `F2-LIVE-001` depends on `F2-004` and still requires explicit owner approval
  of the exact URL before any live request.
- Phase 3-7 tasks remain `pending` until their phase becomes current.
