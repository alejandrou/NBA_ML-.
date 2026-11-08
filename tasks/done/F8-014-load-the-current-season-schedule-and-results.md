---
id: F8-014
title: Load the current season's schedule and results
track: data
areas:
  - scraping
  - data-quality
  - testing
  - documentation
priority: 88
depends_on:
  - F8-003
  - F8-005
  - F8-012
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/domain/BUSINESS_RULES.md
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - src/nba_data/scraping/snapshot_cache.py
  - src/nba_data/scraping/loaders/team_season.py
  - src/nba_data/scraping/parsers/league_schedule.py
  - src/nba_data/scraping/parsers/box_score.py
  - src/nba_data/validation/offline_database.py
  - src/nba_data/db/repositories/core.py
  - src/nba_data/db/models/core.py
validation:
  - uv run pytest tests/unit/test_current_season_identity_loader.py tests/unit/test_current_season_games_loader.py tests/unit/test_game_loader.py tests/unit/test_offline_database_validation.py
  - uv run pytest tests/integration/test_current_season_load_postgres.py tests/integration/test_game_loader_postgres.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Loading the current season into the persistent nba database — only from merged origin/main and with the owner's approval (F8-008). Review uses a disposable database.
---

# Goal

Turn the current season's snapshots and box scores into rows: the 2026-27
season and its 30 team-seasons, every game on the schedule as `scheduled`,
finished games as `final` with their totals and lines, and postponed games
marked, idempotently on every refresh.

# Evidence and current state

- F8-002's `core.games` has `status` in (`scheduled`, `final`, `postponed`) and
  a Basketball Reference game id `<yyyymmdd>0<home code>`.
- An unplayed schedule row has no game link and no points
  (`parsers/league_schedule.py:5`); the id is therefore built from the row's
  date and home team code, the same rule Basketball Reference uses, and checked
  against the link once the game is played.
- F8-005's `backfill games` loads finished games from the archive cache, with
  its cross-table gates.
- `load_team_season_core` (`scraping/loaders/team_season.py:36`) loads a team
  page's season, team, team-season, **and roster**. A 2027 roster would create
  `core.player_seasons` rows that the player-page producers scope by
  (`scraping/player_page_scope.py`), so the coverage oracle would expect 2027
  player statistics that do not exist.
- `validate offline-database` pins archive counts (F8-003: 27 seasons, 805
  team-seasons).

# Human decisions or resources

- [x] **Identity from team pages** (decided 2026-10-18, F8-008): the latest 2027
      team-page snapshots give `core.seasons` (2027) and the 30
      `core.team_seasons`, through the same repository methods as the archive.
      **No roster, no player-season, no team-season statistics** for the
      in-progress season: they change daily and would make the player-page
      coverage oracle expect rows that do not exist. Players enter through box
      score links (F8-005's rule).
- [x] **No `core.game_schedule_versions` table.** History lives in the
      snapshots (F8-012); `core.games` holds the current observation. No
      consumer reads schedule history, so a table would be storage without a
      reader.
- [x] **Status transitions**: new row → `scheduled`; `scheduled` →
      `final` when the box score is cached and passes F8-005's gates;
      `scheduled` → `postponed` when the latest snapshot of the game's month no
      longer lists it at its date, or marks it postponed; `postponed` →
      `scheduled` if it reappears at the same date. A rescheduled game is a new
      id, as Basketball Reference makes it. A `final` row is never changed by a
      refresh: a difference is reported as a conflict and the run fails.
- [x] **Mutable fields of a scheduled row**: `start_time_et`, `venue`,
      `neutral_site` (still `NULL`). Nothing else.
- [x] **The archive validator excludes the current season**: its counts cover
      `season_year <= ARCHIVE_LAST_SEASON` (2026); a separate check requires
      exactly 30 team-seasons, zero player-seasons, and zero official
      team-season stat rows for 2027.

# Acceptance criteria

- `nba-data backfill current-season-identity --season 2027`: loads season and
  team-seasons only, from the latest snapshots; reruns write nothing; refuses a
  season other than `CURRENT_SEASON_END_YEAR` and a team page whose code is not
  a 2026 code.
- `nba-data backfill current-season-games --season 2027 --as-of YYYY-MM-DD
  [--output]`: applies the transitions above; finished games reuse F8-005's
  loader and gates unchanged; reports counts per status and per transition;
  reruns on the same snapshots write nothing.
- A played row whose link id differs from the built id fails the run.
- `validate offline-database` passes on an archive with a loaded 2027 identity,
  and `validate build-stats-coverage` and `validate official-stats` stay green
  (integration test on a disposable rebuild fixture).
- Tests: a first load; a later refresh that finishes three games, postpones
  one, and moves one's start time; a postponed game rescheduled under a new id;
  a conflicting change to a `final` row; a missing box score for a scored row
  (stays `scheduled`, reported); a neutral-site Cup game.
- `BUSINESS_RULES.md` records the transitions; `OFFLINE_DATABASE_PREPARATION.md`
  the current-season exclusion.

# Scope

`src/nba_data/scraping/` current-season loaders (new modules), `cli/main.py`
(two `backfill` commands), `validation/offline_database.py`, their unit and
integration tests, `docs/domain/BUSINESS_RULES.md`,
`docs/validation/OFFLINE_DATABASE_PREPARATION.md`.

# Out of scope

Any fetch (F8-013, F8-008). Rosters and player statistics for the in-progress
season. Schema changes beyond what F8-002 already holds. Predictions (F8-010).

# Impact

- `core.games` gains `scheduled` and `postponed` rows for 2027.

# Cross-track impact

- Additive, no new contract: `F6-020` already serves all three statuses. Recorded
  under `## Open` in `tasks/CROSS_TRACK.md`, because `F6-020` is not done. Once
  2027 is loaded, `core.seasons` also lists it, with 30 team-seasons and no
  player-seasons.

# Implementation notes

- Build the id from the schedule's home team link code, never from a name.
- Run order on a refresh: identity (only the first time) → games.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md`, `docs/validation/OFFLINE_DATABASE_PREPARATION.md`.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_current_season_identity_loader.py tests/unit/test_current_season_games_loader.py tests/unit/test_game_loader.py tests/unit/test_offline_database_validation.py` plus the season-scope tests
- Result: all passed (198 tests in the focused run, including the official-stats and player-scope files).
- Command: `uv run ruff check .`
- Result: All checks passed.
- Command: `uv run mypy src/nba_data`
- Result: no issues in 111 source files.
- Command: `uv run pytest`
- Result: 1816 passed, 260 skipped. The skips are the PostgreSQL lane, run by the next command.
- Command: `bash scripts/validate_database.sh`
- Result: 261 passed on disposable `nba_test_tmp_672749b59d1f44e4`, including `tests/integration/test_current_season_load_postgres.py`; the database was dropped afterwards.
- Command: `uv run python scripts/validate_tasks.py`
- Result: Task validation passed.
- Not run: `uv run pytest tests/integration/...` on its own (the disposable lane above covers those files). Nothing was loaded into `nba`, and no page was fetched.

## Manual happy path

Run against a disposable database whose name starts with `nba_test`, with `DATABASE_URL` naming it. The real 2027
snapshots do not exist until F8-008's first refresh, so steps 2-3 need them or a
hand-built snapshot root.

1. `uv run nba-data backfill current-season-identity --season 2027 --execute-approved-current-season-load`
2. `uv run nba-data backfill current-season-games --season 2027 --as-of 2026-11-08 --output reports/f8-014/current-season.json --execute-approved-current-season-load`
3. Run both commands again.

Expected result: step 1 reports 1 season and 30 team-seasons created. Step 2
reports `new->scheduled` and `scheduled->final` counts and statuses, and exits 0.
Step 3 reports zero created and an empty `transitions`.

## Manual sad path

1. `uv run nba-data backfill current-season-identity --season 2026 --execute-approved-current-season-load`
2. `uv run nba-data backfill current-season-games --season 2027 --as-of 2026-07-01 --execute-approved-current-season-load`
3. With no snapshots in `SCRAPER_SNAPSHOT_DIR`, run either command for 2027 with the flag.
4. With `DATABASE_URL` naming `nba`, run either command with the flag from this branch.
5. Run either command without the flag.

Expected result: steps 1-4 print `Error: ...`, exit 1, and write nothing; step 4 names `HEAD` or uncommitted changes and does not connect. Step 5 exits 2 and does not connect.

## Known limitations

- `neutral_site` stays NULL on every 2027 game, `final` included, so the predictor treats those games as home games and counts them as undetermined. F8-005's inference needs a whole season's venues, and running it later would change `final` rows. An end-of-season pass would need its own decision.
- The checkout guard reads the local `origin/main` ref and does not fetch. It cannot tell whether the owner approved a run: `--execute-approved-current-season-load` records that decision, and the rule that only the owner authorizes it stays procedural.
- `build-stats-coverage` reads only the cache, so loading 2027 cannot change it; only `validate official-stats` and the producers needed the archive scope.
- An unreadable start time on any schedule row refuses the whole run, so one bad row blocks the refresh until the snapshot is corrected.
- F8-021's page identity validation is not done. A team page must name a team, but its name is not compared with the schedule.

## Changes outside the stated scope

- `db/repositories/queries/seasons.py`, `scraping/player_page_scope.py`, `validation/official_stats.py`: without an archive-only scope, loading 2027 would bring the 336 cached 2027 player rows into scope and fail both producers and `validate official-stats`.
- `scraping/current_season_planning.py`: adds `require_latest_month_pages`; the existing planning is unchanged.
- `db/load_guard.py` and `--execute-approved-current-season-load` on both commands: review finding, the card specified no guard. `tasks/backlog/F8-008-keep-the-current-season-current.md` validation commands carry the flag.
