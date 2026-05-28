# Current Work

Status: phase_4c_f4c_003_needs_review

## Active Task

- `F4C-003`: Add offline load reporting and quarantine workflow is
  `needs_review`.
- `F4C-001` is reviewed and marked `done`.
- `F4C-002` is reviewed and marked `done`.

## Current Phase

- Phase ID: `phase-4c-offline-cached-html-processing-and-load`.
- Phase status: `in_progress`.
- Phase 4B controlled raw HTML backfill is closed.
- Phase 4 SQLAlchemy migration is closed and merged through PR #6.
- `F4-001`, `F4-002`, and `F4-003` are `done`.

## Latest Checkpoint

- Owner explicitly approved starting `F4C-003` after startup inspection.
- Startup inspection confirmed source-of-truth consistency:
  `CURRENT_PHASE.md` and `tasks/feature-list.json` point to Phase 4C
  `in_progress`; `F4C-001` and `F4C-002` are `done`; no other task is
  `approved` or `in_progress`.
- Added the missing
  `specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md`.
- Promoted `F4C-003` through the allowed task path for this approved session and
  moved it to `needs_review` after implementation and focused checks.
- Added `src/nba_data/scraping/offline_reporting.py`.
- Added `tests/unit/test_offline_reporting.py`.
- Extended offline processor entry results with parsed row counts and
  quarantined rows for validation failures while keeping invalid rows out of
  `validated_rows`.
- Extended offline loader entry results with quarantined rows for failed loader
  entries.
- Added an audit report builder that combines processing and load reports and
  distinguishes parsed, validated, loaded, skipped, and quarantined rows.
- Added source-context-rich quarantine entries with retry hints for validation,
  processing, and loader failures.
- Updated `docs/validation/TEAM_SEASON_PIPELINE.md` with the operator retry
  workflow.
- Confirmed focused validation passed:
  `uv run pytest tests/unit/test_offline_reporting.py tests/unit/test_offline_processor.py tests/unit/test_offline_loader.py`
  passed with 19 tests.
- Confirmed focused Ruff passed for the touched code and test modules.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- First `uv run pytest` attempt timed out before returning output; reran with a
  longer timeout.
- `uv run pytest`: passed, 106 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Next Safe Action

- Review `F4C-003` against
  `specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md`.
- If approved, mark `F4C-003` as `done`.
- Do not run live scraping, contact Basketball Reference, refresh cache
  misses, delete data, run destructive migrations, add DB tables or lineage
  columns, delete Peewee/legacy code, create another branch, commit, push, open
  a PR, or implement API/frontend/OVR/ranking/similarity/ML work without
  explicit owner approval.

## Suggested Continuation Prompt

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Branch: feature/phase-4c-offline-cached-html-processor

Follow the repo startup protocol first:
1. Read AGENTS.md.
2. Run C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh.
3. Read docs/ai/WORKFLOW_PROTOCOL.md.
4. Read docs/roadmap/PHASE_GOVERNANCE.md.
5. Read docs/roadmap/CURRENT_PHASE.md.
6. Read tasks/feature-list.json.
7. Read specs/phases/phase-4c-offline-cached-html-processing-and-load.md.
8. Read specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md.
9. Read progress/current.md, progress/history.md, and progress/review.md.
10. Run git status --short --branch.

Context:
- Phase 4C is current:
  current_phase_id = phase-4c-offline-cached-html-processing-and-load
  current_phase_status = in_progress
- F4C-001 is reviewed and marked done.
- F4C-002 is reviewed and marked done.
- F4C-003 is implemented and currently needs_review.
- F4C-003 added:
  - specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md
  - src/nba_data/scraping/offline_reporting.py
  - tests/unit/test_offline_reporting.py
- F4C-003 updated:
  - src/nba_data/scraping/offline_processor.py
  - src/nba_data/scraping/offline_loader.py
  - docs/validation/TEAM_SEASON_PIPELINE.md
  - docs/roadmap/CURRENT_PHASE.md
  - docs/roadmap/TASKS.md
  - docs/roadmap/CHANGELOG_LEARNING.md
  - progress/current.md
  - progress/history.md
  - tasks/feature-list.json
- The audit/quarantine report combines processing and load reports and
  distinguishes parsed, validated, loaded, skipped, and quarantined rows.
- Processor validation failures preserve quarantined rows separately from
  validated rows; invalid rows stay out of loader input.
- Loader failures preserve quarantined rows for the failed entry.
- Quarantine entries include source URL, cache path, team abbreviation, season
  year, error/validation details, and retry hints.
- Latest validation:
  - python -m json.tool tasks/feature-list.json: passed
  - uv run ruff check .: passed
  - uv run pytest: first attempt timed out before output; rerun passed with
    106 passed, 1 skipped, 6 Peewee deprecation warnings
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed,
    106 passed, 1 skipped, 6 Peewee deprecation warnings

Guardrails:
- No live scraping.
- Do not contact Basketball Reference.
- Do not refresh cache misses.
- Do not add migrations, DB tables, DB lineage columns, destructive DB changes,
  or data deletion.
- Do not delete raw HTML, database records, volumes, Peewee, or legacy code.
- No API/frontend/OVR/ranking/similarity/ML.
- Do not create another branch, commit, push, or open a PR without explicit
  owner approval.

Task:
1. Review the F4C-003 diff against its feature spec and acceptance criteria.
2. If it is correct, update progress/review.md, mark F4C-003 done, and update
   progress/current.md, progress/history.md, docs/roadmap/TASKS.md,
   docs/roadmap/CURRENT_PHASE.md, docs/roadmap/CHANGELOG_LEARNING.md, and
   tasks/feature-list.json.
3. If you find an issue, mark F4C-003 changes_requested and implement only the
   smallest corrective fix.
4. Run offline validation after review or fixes:
   - python -m json.tool tasks/feature-list.json
   - uv run ruff check .
   - uv run pytest
   - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh
5. Do not start a new phase or any API/frontend/OVR/ranking/similarity/ML work.
```
