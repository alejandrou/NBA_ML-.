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
- `F4E-001`: Plan official wide stats schema.
- `F4E-002`: Stats models and Alembic migration.

## Current

- Current phase: `phase-4e-official-wide-stats-persistence`.
- Current phase status: `in_progress`.
- `F4E-003` through `F4E-006` remain `pending`.

## Next

- Next safe action: commit and push the completed `F4E-002` checkpoint.
- After that push succeeds, promote `F4E-003` and start the stats repository
  task.
- Do not rerun live acquisition, fetch extra HTML, contact Basketball
  Reference again, refresh or overwrite cache hits, create a branch, commit,
  push, open a PR, or implement F5/API/frontend/OVR/ranking/similarity/
  recommendations/ML work without separate explicit owner approval.

## Later

- Phase 4E continues with repositories, loader, offline stats backfill, and
  validation only after each prior F4E task is approved.
- Phase 5-7 tasks remain `pending` until Phase 4E is complete, unless the
  owner explicitly approves a core-only API transition.
