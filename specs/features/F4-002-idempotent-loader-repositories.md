# F4-002 - Idempotent Loader Repositories

## Goal

Add the first SQLAlchemy repository and loader slice for core team-season
identity data. The loader starts from already-normalized rows and writes only
core identity and membership records idempotently.

## Requirements

- Use SQLAlchemy 2.0 repositories with portable select-then-insert/update logic.
- Do not use dialect-specific upserts for this task.
- Validate normalized rows and duplicate natural keys before any database write.
- Do not call `session.commit()` from loaders or repositories.
- Let callers own transaction boundaries and rollback behavior.
- Use existing F4-001 core tables and constraints.
- Keep non-real-team markers such as `TOT` out of real team tables.
- Keep player names descriptive; never use `player_name` as an identity key.
- Preserve meaningful existing team and player names when inputs are fallback
  or empty.

## Acceptance Criteria

- Core repository methods can idempotently create or update seasons, teams,
  team aliases, team seasons, players, player seasons, and player-team seasons.
- `load_team_season_core(...)` can be rerun safely for the same batch.
- Invalid batches perform no database writes.
- Duplicate natural keys fail before any database write.
- Loader and repository methods do not call `session.commit()`.
- Caller rollback removes inserted records.
- Existing meaningful team and player names are not overwritten by fallback or
  empty values.
- `TOT` aggregate rows create player-season records but no real team,
  team-season, or player-team-season rows.
- SQLite unit tests cover idempotency, duplicate input, rollback, name
  overwrite behavior, and `TOT` handling.
- PostgreSQL integration smoke test reruns the same batch twice through the
  real migrated schema without duplicate core rows.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference requests.
- Cached HTML processing or Phase 4C execution.
- Stats tables or official stat loading.
- New Alembic migrations unless a real constraint gap is discovered.
- Data deletion, DB reset, or destructive migration.
- API, frontend, OVR, ranking, similarity, or ML work.
- Peewee or legacy scraper removal.
