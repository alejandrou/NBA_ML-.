# Current Work

Status: phase_4e_f4e_004_needs_review

## Active Task

- `F4E-004`: Normalized rows to wide stats loader.
- Status: `needs_review`.
- `F4E-001` is `done` by explicit owner approval of the reviewed schema plan.
- `F4E-002` is `done` by explicit owner approval of the reviewed models,
  Alembic migration, and tests.
- `F4E-003` is `done` by explicit owner approval of the reviewed repositories,
  tests, and validation.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `in_progress`.
- Phase 4E remains pre-API.

## Latest Checkpoint

- Committed and pushed the completed `F4E-002` and `F4E-003` checkpoints before
  starting loader work.
- Promoted `F4E-004` through `ready`, `approved`, and `in_progress` by explicit
  owner approval to start the normalized-row stats loader task.
- Added `src/nba_data/scraping/loaders/team_season_stats.py` with a
  normalized-row stats loader and JSON-safe per-row load report.
- Exported `load_team_season_stats`, `TeamSeasonStatsLoadEntry`, and
  `TeamSeasonStatsLoadReport` from `src/nba_data/scraping/loaders/__init__.py`.
- The loader routes roster, all team-stint stat tables, and all aggregate
  player-season stat tables through `StatsRepository`.
- The loader resolves existing `core` grains, reports missing identities as
  skipped rows, rejects unknown/protected values, rejects duplicate destination
  grains before stats writes, and uses caller-owned transactions with
  row-level savepoints.
- Added `tests/unit/test_team_season_stats_loader.py` covering routing,
  idempotency, type conversion, roster, `TOT` separation, missing identities,
  duplicate input, unsupported rows, report serialization, no network/parser
  boundaries, and transaction ownership.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- Focused `F4E-004` Ruff check on the stats loader and tests: passed.
- `uv run pytest tests/unit/test_team_season_stats_loader.py`: passed,
  35 passed.
- `uv run pytest`: passed, 234 passed and 6 Peewee deprecation warnings.
- `uv run alembic upgrade head`: passed.
- `uv run alembic check`: passed with no new upgrade operations detected.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  234 passed and 6 Peewee deprecation warnings.

## Guardrails Observed

- The loader does not create `core` rows, own transaction commits or rollbacks,
  run live scraping, refresh cache, wire stats backfills, or import parser,
  normalizer, cache, client, acquisition, CLI, API, frontend, or generated
  metric boundaries.
- No live scraping, Basketball Reference contact, cache refresh, backfill
  command, API/frontend/generated metric work, destructive migration, data
  deletion, Peewee removal, branch creation, or PR occurred.

## Next Safe Action

Review `F4E-004`. After owner approval, close it as `done` and start
`F4E-005` only with explicit approval. Keep `F4E-005` and `F4E-006` pending.
