# Current Work

Status: phase_4e_f4e_003_needs_review

## Active Task

- `F4E-003`: Idempotent stats repositories.
- Status: `needs_review`.
- `F4E-001` is `done` by explicit owner approval of the reviewed schema plan.
- `F4E-002` is `done` by explicit owner approval of the reviewed models,
  Alembic migration, and tests.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `in_progress`.
- Phase 4E remains pre-API.

## Latest Checkpoint

- Committed and pushed the completed `F4E-002` checkpoint before starting
  repository work.
- Promoted `F4E-003` through `ready`, `approved`, and `in_progress` by explicit
  owner approval to start the idempotent stats repository task.
- Added `src/nba_data/db/repositories/stats.py` with explicit idempotent
  upsert wrappers for roster, all team-stint stats tables, and all aggregate
  player-season stats tables.
- Exported `StatsRepository`, `TeamStintStatsUpsert`, and
  `PlayerSeasonStatsUpsert` from `src/nba_data/db/repositories/__init__.py`.
- Added `tests/unit/test_stats_repositories.py` covering inserts, reruns,
  all 17 wrappers, duplicate batch grains, protected/unknown columns, wrong
  grain routing, missing core grains, caller rollback, no transaction
  ownership, and no network/scraping/loader boundaries.
- Added `src/nba_data/db/models/stats.py` with the 17 reviewed `stats` tables:
  `stats.player_team_season_roster`, 8 team-stint stats tables, and 8
  aggregate player-season stats tables.
- Exported all stats models from `src/nba_data/db/models/__init__.py`.
- Updated `alembic/env.py` so Alembic metadata includes `stats`.
- Added Alembic revision `0003_stats_wide_tables` after
  `0002_core_team_player_season`.
- The migration creates schema `stats` and all 17 additive tables with
  deterministic FK and unique constraint names.
- Added `tests/unit/test_stats_models.py` covering metadata registration,
  schemas, FKs, unique constraints, lineage columns, nullability, key types,
  and absence of JSONB.
- Updated the existing PostgreSQL integration test so the additive `0003` head
  remains compatible with the core loader test.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest tests/unit/test_stats_repositories.py`: passed, 31 passed.
- `uv run pytest`: passed, 199 passed and 6 Peewee deprecation warnings.
- `uv run alembic upgrade head`: passed.
- `uv run alembic check`: passed with no new upgrade operations detected.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  199 passed and 6 Peewee deprecation warnings.

## Guardrails Observed

- No loaders, backfill commands, CLI stats commands, API endpoints, frontend
  pages, generated metrics, OVR, rankings, similarity, recommendations, or ML
  work were introduced.
- Stats repositories do not call `session.commit()` or `session.rollback()`,
  do not create `core` rows, and do not import network, scraping, parser,
  normalizer, cache, acquisition, or loader boundaries.
- No live scraping, Basketball Reference contact, cache refresh, data deletion,
  destructive migration, Peewee removal, branch creation, or PR occurred during
  `F4E-003` implementation.

## Next Safe Action

Review `F4E-003`. After approval and validation, close it as `done` and
promote `F4E-004` only when the owner approves starting the normalized rows to
wide stats loader task.
