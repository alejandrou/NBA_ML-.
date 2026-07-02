# Current Work

Status: phase_4e_f4e_008_needs_review

## Active Task

- `F4E-007`: Player-page regular-season aggregate stats backfill is `needs_review`.
- `F4E-006`: Official stats validation checks is `changes_requested`.
- `F4E-008`: Postseason stats schema and player-page backfill is `needs_review`.
- `F4E-009`: Official stats final validation and database closure is
  `pending`.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `in_progress`.
- Phase 4E remains pre-API.

## Latest Checkpoint

- Implemented separate postseason `stats.player_postseason_*` and
  `stats.player_team_postseason_*` SQLAlchemy models plus additive Alembic
  revision `0005_postseason_stats_tables`.
- Added postseason repository wrappers, route families, player-page parser
  support for all required `_post` table IDs, and postseason normalization that
  loads one aggregate row plus all real-team rows without mixing regular season
  and postseason tables.
- Added the cache-only guarded `nba-data backfill player-postseason-stats`
  command and postseason backfill report fields for aggregate/team loads,
  skipped rows, unresolved grains, and unsupported `TOT` rows.
- Added fixture-based postseason parser, normalizer, loader, repository,
  model, and backfill tests for Harden-style `BRK` and Brown-style `BOS`
  playoff cases.
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

- Focused `uv run ruff check` on the postseason models, repositories, parser,
  normalizer, loader, backfill, CLI, migration, and tests: passed.
- `uv run pytest tests/unit/test_player_page_parser.py
  tests/unit/test_player_page_normalizer.py
  tests/unit/test_player_page_stats_loader.py
  tests/unit/test_offline_player_postseason_stats_backfill.py
  tests/unit/test_stats_models.py
  tests/unit/test_stats_repositories.py`: passed, 78 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 305 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `uv run alembic upgrade head`: passed.
- `uv run alembic check`: passed with no new upgrade operations detected.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  305 passed, 1 skipped, and 6 Peewee deprecation warnings.
- `docker compose up -d postgres`: passed after Docker Desktop became
  available.

## Guardrails Observed

- No live scraping, Basketball Reference contact, cache refresh,
  API/frontend/generated metric work, destructive migration, data deletion,
  Peewee removal, branch creation, commit, push, or PR occurred.
- Untracked `NBA.zip` was left untouched.

## Next Safe Action

Review `F4E-007` and `F4E-008`, then proceed to `F4E-009`. Final validation
and database closure remain blocked until `F4E-009`. Keep Phase 5 pending
until Phase 4E closes through `F4E-009`.
