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
- `F4C-001`: Implement offline cached HTML processor is reviewed and marked
  `done`.
- `F4C-002`: Connect offline processor to idempotent loaders is reviewed and
  marked `done`.

## Current

- Current phase: `phase-4c-offline-cached-html-processing-and-load`.
- Current phase status: `in_progress`.
- `F4C-001`: Implement offline cached HTML processor is `done`.
- `F4C-002`: Connect offline processor to idempotent loaders is
  `done`.
- `F4C-003`: Add offline load reporting and quarantine workflow is
  `needs_review`.

## Needs Review

- `F4C-003`: Add offline load reporting and quarantine workflow.

## Next

- Next safe action: review `F4C-003` and either close it as `done` after
  approval and validation or request the smallest corrective change.
- Do not delete data, delete Peewee/legacy code, contact Basketball Reference,
  run live scraping, refresh cache misses, add migrations, add DB tables or
  lineage columns, or implement API/frontend/OVR/ranking/similarity/ML work
  without exact owner approval.

## Later

- Phase 5-7 tasks remain `pending` until explicitly approved under phase
  governance.
