# Current Work

Status: phase_4e_f4e_007_needs_review

## Active Task

- `F4E-007`: Player-page regular-season aggregate stats backfill is `needs_review`.
- `F4E-006`: Official stats validation checks is `changes_requested`.
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
- Fixed the task-board dependency gap so `F4E-007` depends on `F4E-005`, not
  unresolved `F4E-006` review closure.
- Documented the exact `F4E-007` player-page row selection rule: use one
  full-season row per player-season table, prefer `2TM`/`3TM`/`4TM` when
  present, otherwise use the single real-team row.
- Clarified that final validation and database closure stay blocked until
  `F4E-009`, which now owns the closure dependency on `F4E-006`, `F4E-007`,
  and `F4E-008`.
- Implemented cache-only player-page regular-season parsing for
  `totals_stats`, `per_game_stats`, `per_minute_stats`, `per_poss`,
  `advanced`, `shooting`, `adj_shooting`, and `pbp_stats`.
- Added player-page row selection that loads exactly one official full-season
  row per player, season, and table: prefer `2TM`/`3TM`/`4TM`, otherwise use
  the single real-team row, and ignore unsupported `TOT`.
- Added a new Alembic migration and SQLAlchemy model support for nullable
  `source_team_code` on all `stats.player_season_*` regular-season tables
  without adding foreign keys or changing team-stint tables.
- Added idempotent player-page aggregate loading and the guarded
  `nba-data backfill player-stats` cache-only CLI path.
- Added fixture-based parser, selector, loader, backfill, model, and
  repository tests for Harden-style and Brown-style regular-season cases.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 277 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `uv run alembic upgrade head`: passed.
- `uv run pytest` after PostgreSQL-backed validation path was available:
  passed, 278 passed, and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  278 passed and 6 Peewee deprecation warnings.
- `docker compose up -d postgres`: passed after Docker Desktop became
  available.

## Guardrails Observed

- No live scraping, Basketball Reference contact, cache refresh,
  API/frontend/generated metric work, destructive migration, data deletion,
  Peewee removal, branch creation, commit, push, or PR occurred.
- Untracked `NBA.zip` was left untouched.

## Next Safe Action

Review `F4E-007` for acceptance and then proceed to `F4E-008`. Final
validation and database closure remain blocked until `F4E-009`. Keep Phase 5
pending until Phase 4E closes through `F4E-009`.
