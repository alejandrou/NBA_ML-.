# Current Work

Status: phase_4d_approved_f4d_001_ready

## Active Task

- No active task.
- `F4D-001` is `ready`.
- `F4D-002`, `F4D-003`, and `F4D-004` are `pending`.

## Current Phase

- Phase ID: `phase-4d-full-offline-database-preparation`.
- Phase status: `approved`.
- Phase 4C offline cached HTML processing and load is closed.
- `F4C-001`, `F4C-002`, and `F4C-003` are reviewed and marked `done`.
- Phase 4D is a pre-API, offline-only database preparation phase.

## Latest Checkpoint

- Introduced Phase 4D as the next phase after Phase 4C.
- Added a Phase 4D phase spec for full offline database preparation and
  backfill readiness.
- Added Phase 4D task specs for:
  - `F4D-001`: Cached HTML inventory.
  - `F4D-002`: Full offline backfill command.
  - `F4D-003`: Data quality validation checks.
  - `F4D-004`: API-ready database readiness documentation.
- Updated `tasks/feature-list.json` so Phase 4D is current with status
  `approved`.
- Moved only the first Phase 4D task, `F4D-001`, to `ready`.
- Kept `F4D-002`, `F4D-003`, `F4D-004`, Phase 5, Phase 6, and Phase 7 tasks
  `pending`.
- Did not implement Phase 4D runtime code.
- Did not run live scraping, contact Basketball Reference, refresh cache
  misses, write database rows, delete data, run migrations, implement API,
  implement frontend, or add generated metrics work.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 106 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- First `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh` run
  failed because the new Phase 4D spec files were untracked by Git and the
  harness enforces tracking for required files.
- Staged only the Phase 4D planning files touched in this checkpoint.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Next Safe Action

- After validation, request owner approval before implementing `F4D-001`.
- `F4D-001` must only inventory existing cached `.html.gz` files and must not
  write to the database, scrape, refresh cache misses, or contact Basketball
  Reference.
- Do not start `F4D-002`, run a backfill, run live scraping, contact Basketball
  Reference, refresh cache misses, delete raw HTML, delete database records,
  delete Docker/PostgreSQL volumes, run destructive migrations, remove Peewee or
  legacy code, implement API/frontend/OVR/ranking/similarity/recommendations/ML,
  create a branch, commit, push, or open a PR without explicit owner approval.
