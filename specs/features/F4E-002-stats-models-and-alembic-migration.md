# F4E-002 - Stats Models and Alembic Migration

## Goal

Implement the reviewed `stats` schema with SQLAlchemy 2.0 models and an
additive Alembic migration after the F4E-001 schema plan is approved.

## Preconditions

- `F4E-001` is reviewed and approved.
- Phase 4D core relational database readiness is closed.
- Current Alembic head is `0002_core_team_player_season`.
- No further schema design decisions are required beyond
  `docs/architecture/OFFICIAL_STATS_SCHEMA.md`.

## Requirements

- Add `src/nba_data/db/models/stats.py`.
- Export all stats models from `src/nba_data/db/models/__init__.py`.
- Create an Alembic revision after `0002_core_team_player_season`.
- Create schema `stats` through Alembic, not `create_tables()`.
- Add the initial 17 regular-season tables documented in
  `docs/architecture/OFFICIAL_STATS_SCHEMA.md`:
  `stats.player_team_season_roster`, 8 `player_team_season_*` stats tables,
  and 8 `player_season_*` aggregate stats tables.
- Every roster/team-stint table has non-null
  `player_team_season_id -> core.player_team_seasons.id` and a unique
  constraint on `player_team_season_id`.
- Every aggregate table has non-null
  `player_season_id -> core.player_seasons.id` and a unique constraint on
  `player_season_id`.
- Every table has `id`, the FK grain column, `source_url`, `cache_path`,
  `parser_version`, `created_at`, and `updated_at`.
- Use the reviewed final column names and SQL types from
  `docs/architecture/OFFICIAL_STATS_SCHEMA.md`.
- Official stat columns are nullable by default.
- PK, FK grain, and lineage columns are non-null.
- Do not use `JSONB` as primary stat storage.
- Do not modify or destructively migrate `core`.
- The unique FK constraint backing index is the lookup index for the table
  grain; do not add duplicate non-unique FK indexes.

## Suggested Constraint Names

Use deterministic names so tests and review can verify intent:

- `uq_stats_<table>_player_team_season_id` for roster/team-stint tables.
- `uq_stats_<table>_player_season_id` for aggregate tables.
- `fk_stats_<table>_player_team_season_id` for team-stint FKs.
- `fk_stats_<table>_player_season_id` for aggregate FKs.

## Acceptance Criteria

- SQLAlchemy metadata includes all 17 reviewed `stats` tables.
- Alembic upgrade creates the `stats` schema and all wide tables.
- Alembic downgrade reverses the additive `stats` schema changes where
  practical.
- FKs and unique constraints target the reviewed `core` grains.
- Tests cover model metadata, FK targets, uniqueness, nullable stat fields,
  lineage columns, timestamp defaults, reviewed type choices, and absence of
  primary `JSONB` stat storage.
- No repositories, loaders, backfill commands, API endpoints, frontend, or
  generated metrics are introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `uv run alembic upgrade head`
- `uv run alembic check`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh.
- Loading stats rows.
- Data deletion or destructive migrations.
- Peewee or legacy scraper removal.
- Stats repositories, loaders, or backfill execution.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.
