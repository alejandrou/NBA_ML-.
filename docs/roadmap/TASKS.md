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
- Phase 4D full offline database preparation is complete and reviewed.
- `F4D-ACQ-001`: Generate NBA team-season URL manifest and dry-run plan.
- `F4D-ACQ-LIVE-001`: Run owner-approved controlled NBA team-season cache
  acquisition.
- `F4D-ACQ-002`: Review acquisition report and cache coverage handoff.
- `F4D-001`: Build cached HTML inventory.
- `F4D-002`: Add full offline backfill command.
- `F4D-003`: Add post-load data quality validation checks.
- `F4D-004`: Document API-ready database readiness workflow.

## Current

- Current phase: `phase-4d-full-offline-database-preparation`.
- Current phase status: `done`.
- No active implementation task.
- No task is in `needs_review`.

## Next

- Next safe action: prepare a Phase 4D to Phase 4E transition summary and wait
  for explicit owner approval before promoting any Phase 4E task.
- `F4E-001` through `F4E-006` remain `pending`.
- Do not rerun live acquisition, fetch extra HTML, contact Basketball
  Reference again, refresh or overwrite cache hits, create a branch, commit,
  push, open a PR, or implement F4E/F5/API/frontend/stats persistence/OVR/
  ranking/similarity/recommendations/ML work without separate explicit owner
  approval.

## Later

- Proposed Phase 4E has been prepared as a future official wide stats
  persistence phase. It is not active.
- Phase 5-7 tasks remain `pending` until Phase 4D and any approved pre-API
  stats work are reviewed and approved for closure and the owner explicitly
  approves an API transition.
