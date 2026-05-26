# F4-001 - Core Team Player Season SQLAlchemy Migrations

## Goal

Add reviewed SQLAlchemy and Alembic schema support for core team, player, and
season relationships while preserving Peewee and legacy scraper coexistence.

## Requirements

- Add additive SQLAlchemy 2.0 models under the `core` schema.
- Add a reversible Alembic migration after `0001_initial_raw_core`.
- Preserve existing Peewee models and legacy scraper code.
- Keep `TOT` out of real team identifier tables.
- Do not implement loaders, stats tables, API/frontend work, or generated
  metrics.

## Acceptance Criteria

- `core.team_seasons` links a real team to a season, is unique by team-season
  and season-abbreviation, and rejects `TOT`.
- `core.player_seasons` links a player to a season and is unique by
  player-season.
- `core.player_team_seasons` links a player-season to a team-season stint with
  optional roster number and position only.
- Core team identifiers have stable unique/check constraints.
- Alembic migration downgrade reverses the additive schema changes.
- Offline tests cover metadata, constraints, foreign keys, relationships, and
  model exports.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `uv run alembic upgrade head`
- `uv run alembic check`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference requests.
- Data deletion or destructive migrations.
- Peewee or legacy scraper deletion.
- SQLAlchemy loaders or repository upserts.
- Phase 4C offline processing/load work.
- API, frontend, OVR, ranking, similarity, or ML work.
