# F4E-003 - Idempotent Stats Repositories

## Goal

Add SQLAlchemy repositories that can create or update official wide stats rows
idempotently without owning transaction commits.

## Requirements

- Use SQLAlchemy 2.0 repository methods over the `stats` models introduced in
  F4E-002.
- Use portable select-then-insert/update behavior unless a later reviewed task
  explicitly chooses dialect-specific upserts.
- Do not call `session.commit()` or `session.rollback()` from repositories.
- Upsert team-stint stats by `player_team_season_id`.
- Upsert aggregate `TOT` stats by `player_season_id`.
- Reject attempts to load aggregate rows into team-stint tables or team rows
  into aggregate tables.
- Keep `player_name` and display names descriptive only.
- Do not create or update `core` identity records in stats repositories.

## Acceptance Criteria

- Repository methods cover roster, all team-stint stat tables, and all
  aggregate stat tables.
- Rerunning the same stats input updates the same rows without duplicates.
- Duplicate natural keys in one input batch fail before any write.
- Caller rollback removes inserted stats rows.
- Repository methods do not commit or roll back transactions.
- Tests cover idempotency, duplicate input, rollback behavior, FK grain
  enforcement, and `TOT` separation.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or cache refresh.
- Parser or normalizer changes except tiny test fixtures if needed.
- SQLAlchemy migrations beyond gaps discovered from F4E-002 review.
- Backfill command execution.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.

