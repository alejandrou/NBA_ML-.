# F4E-002 - Stats Models and Alembic Migration

## Goal

Implement the reviewed `stats` schema with SQLAlchemy 2.0 models and an
additive Alembic migration after the F4E-001 schema plan is approved.

## Requirements

- Add a future `src/nba_data/db/models/stats.py` and export the models from the
  package model index.
- Create schema `stats` through Alembic, not `create_tables()`.
- Add `stats.player_team_season_roster`.
- Add team-stint tables:
  `player_team_season_totals`, `player_team_season_per_game`,
  `player_team_season_per_minute`, `player_team_season_per_poss`,
  `player_team_season_advanced`, `player_team_season_shooting`,
  `player_team_season_adj_shooting`, and `player_team_season_pbp`.
- Add aggregate tables:
  `player_season_totals`, `player_season_per_game`,
  `player_season_per_minute`, `player_season_per_poss`,
  `player_season_advanced`, `player_season_shooting`,
  `player_season_adj_shooting`, and `player_season_pbp`.
- Team-stint tables use non-null FK columns to
  `core.player_team_seasons.id`.
- Aggregate tables use non-null FK columns to `core.player_seasons.id`.
- Every table has a surrogate primary key plus a unique constraint on its FK
  grain.
- Official stat columns are typed and nullable by default.
- Do not use `JSONB` as primary stat storage.

## Acceptance Criteria

- SQLAlchemy metadata includes all F4E approved `stats` tables.
- Alembic upgrade creates the `stats` schema and all wide tables.
- Alembic downgrade reverses the additive `stats` schema changes where
  practical.
- FKs, unique constraints, and lookup indexes exist for common
  player-season/team-season API queries.
- Tests cover model metadata, FK targets, uniqueness, nullable stat fields,
  and absence of primary `JSONB` stat storage.
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
- Loading stats rows.
- Data deletion or destructive migrations.
- Peewee or legacy scraper removal.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.

