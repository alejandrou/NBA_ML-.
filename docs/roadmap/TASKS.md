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

## Current

- Current phase: `phase-4b-controlled-raw-html-backfill`.
- Current phase status: `proposed`.
- `F4B-001`, `F4B-002`, `F4B-003`, and `F4B-LIVE-001` are `done`.
- No task is currently `approved`, `in_progress`, or `needs_review`.

## Needs Review

- None.

## Next

- Next safe action: decide whether to close Phase 4B with a transition summary
  or explicitly approve a future task.
- Do not rerun live acquisition, expand the manifest, contact Basketball
  Reference, start Phase 4C, or start Phase 4 SQLAlchemy migration without
  exact owner approval.

## Later

- Phase 4 SQLAlchemy migration remains inactive; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.
- Phase 4C offline cached HTML processing and load remains future work.
- Phase 5-7 tasks remain `pending` until explicitly approved under phase
  governance.
