# F4E-001 - Official Wide Stats Schema Plan

## Goal

Finalize a reviewed relational schema plan for official Basketball Reference
player statistics before any SQLAlchemy models, Alembic migrations, loaders, or
database writes are implemented.

## Requirements

- Document the `core` / `stats` / `features` separation in
  `docs/architecture/OFFICIAL_STATS_SCHEMA.md`.
- Inspect the normalized keys emitted by the current normalizer for every
  supported `source_table`: roster, totals, per-game, per-minute,
  per-possession, advanced, shooting, adjusted shooting, and play-by-play.
- Define wide typed target tables for real team stints and separate aggregate
  `TOT` target tables.
- Use `core.player_team_seasons.id` as the FK grain for real-team stats.
- Use `core.player_seasons.id` as the FK grain for aggregate `TOT` stats.
- Keep `stats.player_team_season_roster` team-stint only.
- Map count fields to integers, rate/percentage/advanced fields to numeric
  decimals, and official display text fields to strings.
- Mark stat columns nullable by default, with non-null FK and unique grain
  columns.
- Require surrogate primary keys and unique FK constraints on every wide table.
- Review legacy `player_stats`, `player_advanced`, and roster ideas without
  copying legacy Peewee identity mistakes.

## Acceptance Criteria

- Phase spec exists at
  `specs/phases/phase-4e-official-wide-stats-persistence.md`.
- Design doc exists at `docs/architecture/OFFICIAL_STATS_SCHEMA.md`.
- Legacy review exists at `docs/migration/LEGACY_STATS_SCHEMA_REVIEW.md`.
- The design lists all team-stint and aggregate table names.
- The design records normalized keys observed from the current normalizer
  before final columns are frozen.
- The design states that `TOT` is persisted only through player-season
  aggregate tables, not team tables.
- The design rejects `JSONB` as primary stat storage.
- No SQLAlchemy stats models, Alembic migrations, loaders, backfills, or
  database writes are introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Implementing `stats` SQLAlchemy models.
- Creating Alembic migrations.
- Implementing repositories, loaders, CLI commands, or backfills.
- Running live scraping, cache refresh, or database writes.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.

