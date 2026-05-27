# Current Work

Status: phase_4c_f4c_002_needs_review

## Active Task

- `F4C-001` is reviewed and marked `done`.
- Owner approved implementing `F4C-002` in this session.
- `F4C-002` was promoted through the allowed task state path and is
  `needs_review`.
- `F4C-003` remains `pending` and must not start automatically after
  `F4C-002`.

## Current Phase

- Phase ID: `phase-4c-offline-cached-html-processing-and-load`.
- Phase status: `in_progress`.
- Phase 4B controlled raw HTML backfill is closed.
- Phase 4 SQLAlchemy migration is closed and merged through PR #6.
- `F4-001`, `F4-002`, and `F4-003` are `done`.

## Latest Checkpoint

- Created the approved `F4C-002` implementation plan.
- Added the `F4C-002` feature spec.
- Implemented the narrow loader orchestration task:
  validated processor entries -> `TeamSeasonLoadBatch` ->
  `load_team_season_core(...)`.
- Source lineage must stay at report/result level only:
  `source_url`, `cache_path`, `team_abbreviation`, and `season_year`.
- Added per-entry savepoint handling so loader failures roll back partial
  writes for that entry.
- Added tests for idempotent reruns, processor failure skips, savepoint
  rollback, source context preservation, no network boundary, and no commit.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest tests/unit/test_offline_loader.py`: passed, 6 passed.
- `uv run ruff check src/nba_data/scraping/offline_loader.py tests/unit/test_offline_loader.py`:
  passed.
- `uv run pytest`: passed, 102 passed, 1 skipped, and 6 Peewee deprecation
  warnings after rerunning with a longer timeout.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 102
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Next Safe Action

- Review `F4C-002` and either close it as `done` after approval or request
  changes.
- Stop before `F4C-003`; do not start it until explicit owner approval after
  `F4C-002` review closure.
- Do not run live scraping, contact Basketball Reference, refresh cache
  misses, delete data, run destructive migrations, delete Peewee/legacy code,
  create another branch, commit, push, open a PR, or implement
  API/frontend/OVR/ranking/similarity/ML work without explicit owner approval.

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
8. Read specs/features/F4C-002-connect-offline-processor-to-idempotent-loaders.md.
9. Read progress/current.md, progress/history.md, and progress/review.md.
10. Run git status --short --branch.

Context:
- Phase 4C is current:
  current_phase_id = phase-4c-offline-cached-html-processing-and-load
  current_phase_status = in_progress
- F4C-001 is reviewed and marked done.
- F4C-002 has been implemented and is now needs_review.
- F4C-003 remains pending and must not start automatically.
- The F4C-002 implementation added:
  - specs/features/F4C-002-connect-offline-processor-to-idempotent-loaders.md
  - src/nba_data/scraping/offline_loader.py
  - tests/unit/test_offline_loader.py
- The offline loader starts from OfflineTeamSeasonProcessingReport entries, not raw HTML.
- It loads only status="validated" entries through TeamSeasonLoadBatch and load_team_season_core(...).
- Processor failure entries are skipped and do not call DB loaders.
- Each validated entry runs inside a nested transaction savepoint.
- Loader orchestration does not call session.commit().
- Source lineage stays at result/report level only:
  source_url, cache_path, team_abbreviation, season_year.
- No migrations, new DB tables, DB lineage columns, F4C-003 reporting/quarantine, API/frontend/OVR/ranking/similarity/ML, live scraping, cache refresh, or Basketball Reference contact were introduced.
- Latest validation passed:
  - python -m json.tool tasks/feature-list.json
  - uv run ruff check .
  - uv run pytest tests/unit/test_offline_loader.py: 6 passed
  - uv run pytest: 102 passed, 1 skipped, 6 Peewee deprecation warnings
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed, 102 passed, 1 skipped, 6 Peewee deprecation warnings

Guardrails:
- No live scraping.
- Do not contact Basketball Reference.
- Do not refresh cache misses.
- Do not start F4C-003 unless I explicitly approve it after F4C-002 review closure.
- Do not add migrations, DB tables, DB lineage columns, destructive DB changes, or data deletion.
- Do not delete raw HTML, database records, volumes, Peewee, or legacy code.
- No API/frontend/OVR/ranking/similarity/ML.
- Do not create another branch, commit, push, or open a PR without explicit owner approval.

Task:
1. Review the F4C-002 diff against its feature spec and acceptance criteria.
2. If correct, update progress/review.md, mark F4C-002 done, and update progress/current.md, progress/history.md, docs/roadmap/TASKS.md, docs/roadmap/CURRENT_PHASE.md, docs/roadmap/CHANGELOG_LEARNING.md, and tasks/feature-list.json.
3. If you find an issue, mark F4C-002 changes_requested and implement only the smallest corrective fix.
4. Run offline validation after review or fixes:
   - python -m json.tool tasks/feature-list.json
   - uv run ruff check .
   - uv run pytest
   - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh
5. Stop after F4C-002 review closure and ask for explicit owner approval before starting F4C-003.
```
