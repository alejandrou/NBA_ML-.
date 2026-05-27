# Current Work

Status: phase_4c_f4c_001_done_waiting_for_f4c_002_approval

## Active Task

- `F4C-001` is reviewed and marked `done`.
- No task is currently `approved`, `in_progress`, or `needs_review`.
- `F4C-002` and `F4C-003` remain `pending`.

## Current Phase

- Phase ID: `phase-4c-offline-cached-html-processing-and-load`.
- Phase status: `in_progress`.
- Phase 4B controlled raw HTML backfill is closed.
- Phase 4 SQLAlchemy migration is closed and merged through PR #6.
- `F4-001`, `F4-002`, and `F4-003` are `done`.

## Latest Checkpoint

- Reviewed `F4C-001` against
  `specs/features/F4C-001-offline-cached-html-processor.md`.
- Approved the implementation and marked `F4C-001` as `done`.
- Confirmed the processor reads existing cached `.html.gz` sources only, then
  parses, normalizes, and validates rows.
- Confirmed URL sources resolve through `HtmlCache.path_for_url`, explicit path
  sources must stay under the cache root, and cache misses fail without cache
  refresh.
- Confirmed the processor does not accept or import `BasketballReferenceClient`,
  `requests`, `httpx`, or a generic network client.
- Confirmed the processor does not write database rows, call SQLAlchemy
  loaders, add migrations, or start `F4C-002`.
- Kept `F4C-002` and `F4C-003` pending.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 96 passed, 1 skipped, and 6 Peewee deprecation
  warnings after rerunning with a longer timeout.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 96
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Next Safe Action

- Wait for explicit owner approval before starting `F4C-002`.
- Do not connect database loaders, write DB loader data from cached HTML, run
  live scraping, contact Basketball Reference, refresh cache misses, delete
  data, run destructive migrations, delete Peewee/legacy code, create another
  branch, commit, push, open a PR, or implement
  API/frontend/OVR/ranking/similarity/ML work without explicit owner approval.
