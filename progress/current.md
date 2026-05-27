# Current Work

Status: phase_4c_f4c_001_needs_review

## Active Task

- `F4C-001` is `needs_review`.
- No task is currently `approved` or `in_progress`.
- `F4C-002` and `F4C-003` remain `pending`.

## Current Phase

- Phase ID: `phase-4c-offline-cached-html-processing-and-load`.
- Phase status: `in_progress`.
- Phase 4B controlled raw HTML backfill is closed.
- Phase 4 SQLAlchemy migration is closed and merged through PR #6.
- `F4-001`, `F4-002`, and `F4-003` are `done`.

## Latest Checkpoint

- Created branch `feature/phase-4c-offline-cached-html-processor` from
  `main`.
- Preserved the existing local Phase 4 merge handoff updates in
  `progress/current.md` and `progress/history.md` while continuing on the new
  branch.
- Activated Phase 4C as the current approved phase.
- Prepared `F4C-001` as the first Phase 4C task with status `ready`, not
  `approved`.
- Created `specs/features/F4C-001-offline-cached-html-processor.md`.
- Updated roadmap/task docs for the Phase 4C transition.
- Owner approved `F4C-001` implementation in this session.
- Moved Phase 4C and `F4C-001` into active implementation state.
- Added `src/nba_data/scraping/offline_processor.py`.
- Added `tests/unit/test_offline_processor.py`.
- The processor accepts URL sources resolved through `HtmlCache.path_for_url`
  and explicit `.html.gz` paths under the cache root.
- The runtime order is cached gzip read, parse, normalize, then validate.
- Cache misses and validation failures produce per-input failures without
  refreshing cache misses or blocking other inputs.
- Successful outputs expose validated normalized rows plus source context.
- Moved `F4C-001` to `needs_review` after validation.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- `uv run pytest tests/unit/test_offline_processor.py`: passed, 9 passed.
- `uv run ruff check src/nba_data/scraping/offline_processor.py tests/unit/test_offline_processor.py`:
  passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 96 passed, 1 skipped, and 6 Peewee deprecation
  warnings after rerunning with a longer timeout.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 96
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Next Safe Action

- Review the `F4C-001` implementation slice and either mark it `done` after
  approval or request the smallest corrective fix.
- Do not start `F4C-002` or connect database loaders until `F4C-001` is
  reviewed and the owner explicitly approves the next task.
- Do not run live scraping, contact Basketball Reference, refresh cache misses,
  write DB loader data from cached HTML, delete data, run destructive
  migrations, delete Peewee/legacy code, create another branch, commit, push,
  open a PR, or implement API/frontend/OVR/ranking/similarity/ML work without
  explicit owner approval.

## Continuation Prompt

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
8. Read specs/features/F4C-001-offline-cached-html-processor.md.
9. Read progress/current.md, progress/history.md, and progress/review.md.
10. Run git status --short --branch.

Context:
- Phase 4 SQLAlchemy migration is closed and merged via PR #6.
- Phase 4C is current:
  current_phase_id = phase-4c-offline-cached-html-processing-and-load
  current_phase_status = in_progress
- F4C-001 has been implemented and is now needs_review.
- F4C-002 and F4C-003 remain pending.
- The F4C-001 implementation added:
  - src/nba_data/scraping/offline_processor.py
  - tests/unit/test_offline_processor.py
- The processor reads only existing .html.gz cache files, then parses,
  normalizes, and validates team-season rows.
- It accepts URL sources resolved through HtmlCache.path_for_url and explicit
  .html.gz paths under the cache root.
- It does not accept BasketballReferenceClient, requests, httpx, or any generic
  network client.
- It does not write database rows or call loaders.
- Cache misses, invalid paths, read errors, and validation failures are
  per-input failures and do not refresh the cache.
- Latest validation passed:
  - python -m json.tool tasks/feature-list.json
  - uv run pytest tests/unit/test_offline_processor.py: 9 passed
  - uv run ruff check .
  - uv run pytest: 96 passed, 1 skipped, 6 Peewee deprecation warnings
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed

Guardrails:
- No live scraping.
- Do not contact Basketball Reference.
- Do not refresh cache misses.
- Do not write DB loader data from cached HTML in F4C-001.
- Do not start F4C-002 or connect database loaders.
- Do not delete raw HTML, database records, volumes, Peewee, or legacy code.
- No destructive migrations.
- No API/frontend/OVR/ranking/similarity/ML.
- Do not create another branch, commit, push, or open a PR without explicit
  owner approval.

Task:
1. Review the F4C-001 diff against its feature spec and acceptance criteria.
2. If it is correct, update progress/review.md, mark F4C-001 done, and update
   progress/current.md, progress/history.md, docs/roadmap/TASKS.md, and
   tasks/feature-list.json.
3. If you find an issue, mark F4C-001 changes_requested and implement only the
   smallest corrective fix.
4. Run offline validation after review or fixes.
5. Do not start F4C-002 unless I explicitly approve it in that session.
```
