# Current Work

Status: phase_4e_f4e_005_needs_review

## Active Task

- `F4E-005`: Offline stats backfill command.
- Status: `needs_review`.
- `F4E-001` is `done` by explicit owner approval of the reviewed schema plan.
- `F4E-002` is `done` by explicit owner approval of the reviewed models,
  Alembic migration, and tests.
- `F4E-003` is `done` by explicit owner approval of the reviewed repositories,
  tests, and validation.
- `F4E-004` is `done` by explicit owner approval of the reviewed normalized-row
  stats loader, tests, and validation.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `in_progress`.
- Phase 4E remains pre-API.

## Latest Checkpoint

- Closed `F4E-004` as `done` by explicit owner approval.
- Promoted `F4E-005` through `ready`, `approved`, and `in_progress` by explicit
  owner approval before implementation.
- Added `src/nba_data/scraping/offline_stats_backfill.py` with a guarded,
  cache-only stats backfill orchestrator and JSON-safe report dataclasses.
- The orchestrator builds the cached HTML inventory, selects only valid entries,
  applies deterministic `team`, `start_year`, `end_year`, and `limit` filters,
  processes local HTML through the existing offline processor, and loads
  validated rows through `load_team_season_stats`.
- Added `nba-data backfill stats`, guarded by
  `--execute-approved-stats-backfill`, with `--output`, `--max-workers`,
  `--limit`, `--team`, `--start-year`, `--end-year`, and `--parser-version`.
- Added `tests/unit/test_offline_stats_backfill.py` covering inventory
  selection, filters, invalid arguments, processor and loader orchestration,
  report aggregation, JSON serialization, CLI guard behavior, output writing,
  no-network/no-core-loader boundaries, savepoint rollback, and idempotent
  rerun behavior through the existing stats loader.

## Latest Validation

- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed before
  starting `F4E-005`.
- Focused Ruff check on the stats backfill module, CLI, and new tests: passed.
- `uv run pytest tests/unit/test_offline_stats_backfill.py`: passed,
  16 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 250 passed and 6 Peewee deprecation warnings.
- `uv run alembic upgrade head`: passed.
- `uv run alembic check`: passed with no new upgrade operations detected.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  250 passed and 6 Peewee deprecation warnings.

## Guardrails Observed

- The stats backfill command is cache-only and guarded by an explicit execution
  flag.
- The orchestrator does not call the core loader, create `core` rows, own
  transaction commits or rollbacks, run live scraping, refresh cache, run
  acquisition, delete data, or import network client boundaries.
- The real stats backfill command was not executed during implementation.
- No live scraping, Basketball Reference contact, cache refresh, acquisition,
  API/frontend/generated metric work, destructive migration, data deletion,
  Peewee removal, branch creation, or PR occurred.

## Next Safe Action

Review `F4E-005`. Keep `F4E-006` pending until the owner approves the official
stats validation checks task.

## Documentation Note

- Added reusable Codex execution and context documentation so future prompts
  can reference repository memory instead of repeating long phase context.
