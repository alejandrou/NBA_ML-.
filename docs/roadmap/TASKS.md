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
- Phase 4B controlled raw HTML backfill is complete and reviewed.
- `F4B-001`: Design controlled raw HTML backfill manifest.
- `F4B-002`: Add raw HTML backfill manifest dry-run validation.
- `F4B-003`: Add sequential cache-first raw HTML acquisition runner.
- `F4B-LIVE-001`: Run owner-approved raw HTML backfill pilot.
- Phase 4 SQLAlchemy migration is complete and reviewed.
- `F4-001`, `F4-002`, and `F4-003` are marked `done`.
- Phase 4C offline cached HTML processing and load is complete and reviewed.
- `F4C-001`: Implement offline cached HTML processor.
- `F4C-002`: Connect offline processor to idempotent loaders.
- `F4C-003`: Add offline load reporting and quarantine workflow.

## Current

- Current phase: `phase-4d-full-offline-database-preparation`.
- Current phase status: `approved`.
- No active task.
- `F4D-001`: Cached HTML inventory is `ready`.

## Needs Review

- None.

## Next

- Next safe action: implement `F4D-001` only after explicit owner approval.
- `F4D-001` must inventory existing cached `.html.gz` files only.
- Do not write database rows, run live scraping, contact Basketball Reference,
  refresh cache misses, delete data, run destructive migrations, create a
  branch, commit, push, open a PR, or implement API/frontend/OVR/ranking/
  similarity/recommendations/ML work without exact owner approval.

## Later

- `F4D-002`: Full offline backfill command remains `pending`.
- `F4D-003`: Data quality validation checks remains `pending`.
- `F4D-004`: API-ready database readiness documentation remains `pending`.
- Phase 5-7 tasks remain `pending` until Phase 4D is reviewed and approved for
  closure and the owner explicitly approves an API transition.
