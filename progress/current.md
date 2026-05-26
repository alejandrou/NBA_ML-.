# Current Work

Status: phase_4_closed_ready_for_commit_push_pr_approval

## Active Task

- `F4-001` is `done`.
- `F4-002` is `done`.
- `F4-003` is `done`.
- No task is currently `approved`, `in_progress`, or `needs_review`.

## Current Phase

- Phase ID: `phase-4-sqlalchemy-migration`.
- Phase status: `done`.
- Phase 4B controlled raw HTML backfill is closed.
- Phase 4 SQLAlchemy migration is closed.
- Phase 4C offline cached HTML processing and load remains pending and is not
  approved.

## Phase 4 Closure Summary

- `F4-001` added additive SQLAlchemy core relationship models and Alembic
  revision `0002_core_team_player_season.py`.
- `F4-003` added the local PostgreSQL database validation path and aligned raw
  timestamp metadata with existing nullable migrations.
- `F4-002` added idempotent SQLAlchemy repositories and
  `load_team_season_core(...)` for already-normalized rows.
- Review confirmed validation and duplicate natural-key checks happen before
  writes, repository logic is portable select-then-insert/update, commits stay
  caller-owned, rollback behavior is covered, meaningful names are preserved,
  `player_name` is not an identity key, and `TOT` aggregate rows do not create
  real team membership records.
- No new Alembic revision was added for `F4-002`.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 88 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  88 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`: passed;
  `alembic check` reported no new upgrade operations and the PostgreSQL smoke
  test passed.
- `uv run alembic current`: `0002_core_team_player_season (head)`.
- `git diff --cached --name-only -- .env data/raw`: passed with no output.

## Next Safe Action

- Prepare commit, push, and PR only after explicit owner approval.
- Do not start Phase 4C, cached HTML processing/loading, live scraping,
  Basketball Reference contact, data deletion, destructive migrations,
  Peewee/legacy deletion, API/frontend, generated metrics, OVR, ranking,
  similarity, or ML work without explicit owner approval.
