# Tasks

## Done

- Phase 1 foundations are complete and reviewed.
- F1-001 through F1-011 are marked `done`.
- Phase 2 scraper-cache integration is complete and reviewed.
- F2-001 through F2-006 and F2-LIVE-001 are marked `done`.
- Phase 3 parser normalization is complete and reviewed.
- `F3-001`: Expand cached team-season table parsers.
- `F3-002`: Normalize parsed team-season rows.
- `F3-003`: Add parser data-quality checks.
- Phase 4A legacy scraper consolidation is complete.
- `F4A-000`: Add legacy parity and acquisition smoke-test strategy.
- `F4A-001`: Consolidate legacy scrapers behind cache-first providers.
- `F4A-002`: Design bounded offline cached HTML processing.
- `F4B-001`: Design controlled raw HTML backfill manifest.
- `F4B-002`: Add raw HTML backfill manifest dry-run validation.
- `F4B-003`: Add sequential cache-first raw HTML acquisition runner.
- `F4B-LIVE-001`: Run owner-approved raw HTML backfill pilot.
- Phase 4B controlled raw HTML backfill is complete and reviewed.
- Phase 4 SQLAlchemy migration is complete and reviewed.
- `F4-001`, `F4-002`, and `F4-003` are marked `done`.

## Current

- Current phase: `phase-4c-offline-cached-html-processing-and-load`.
- Current phase status: `in_progress`.
- `F4C-001`: Implement offline cached HTML processor is `needs_review`.
- `F4C-002`: Connect offline processor to idempotent loaders is `pending`.
- `F4C-003`: Add offline load reporting and quarantine workflow is `pending`.
- No task is currently `approved` or `in_progress`.

## Needs Review

- `F4C-001`: Implement offline cached HTML processor.

## Next

- Next safe action: review the `F4C-001` implementation slice.
- Do not start `F4C-002` loader connection until `F4C-001` is reviewed and the
  owner explicitly approves the next task.
- Do not delete data, delete Peewee/legacy code, contact Basketball Reference,
  run live scraping, refresh cache misses, write DB loader data, or implement
  API/frontend/OVR/ranking/similarity/ML work without exact owner approval.

## Later

- `F4C-002` will connect validated offline processor output to idempotent
  loaders after `F4C-001` is done.
- `F4C-003` will add reporting and quarantine workflow after loader connection.
- Phase 5-7 tasks remain `pending` until explicitly approved under phase
  governance.
