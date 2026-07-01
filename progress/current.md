# Current Work

Status: phase_4e_f4e_007_ready

## Active Task

- No task is currently `in_progress`.
- `F4E-006`: Official stats validation checks is `changes_requested`.
- `F4E-007`: Player-page regular-season aggregate stats backfill is `ready`.
- `F4E-008`: Postseason stats schema and player-page backfill is `pending`.
- `F4E-009`: Official stats final validation and database closure is
  `pending`.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `in_progress`.
- Phase 4E remains pre-API.

## Latest Checkpoint

- Documented the owner-approved source plan update for official stats:
  team-season pages populate `stats.player_team_season_*`, and player pages
  populate `stats.player_season_*`.
- Replaced current full-season source guidance with `2TM`, `3TM`, and `4TM` as
  player-page `source_team_code` metadata markers, not teams.
- Documented that `TOT`, `2TM`, `3TM`, and `4TM` must not appear in
  `core.teams`, `core.team_seasons`, or team-stint stats tables.
- Added future planning for player-page regular-season full-season stats,
  separate postseason stats tables, and final official stats validation.
- Marked `F4E-006` as `changes_requested` because validator/design guidance
  still needs synthetic-code and Basketball Reference numeric-range updates.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- Targeted stale current guidance search: passed for active docs/specs/task
  state.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 259 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  259 passed, 1 skipped, and 6 Peewee deprecation warnings.

## Guardrails Observed

- No runtime code, tests, SQLAlchemy models, Alembic migrations, parsers,
  loaders, DB writes, live scraping, Basketball Reference contact, cache
  refresh, API/frontend/generated metric work, destructive migration, data
  deletion, Peewee removal, branch creation, commit, push, or PR occurred.
- Untracked `NBA.zip` was left untouched.

## Next Safe Action

Approve and start `F4E-007` when ready. Keep Phase 5 pending until Phase 4E
closes through `F4E-009`.
