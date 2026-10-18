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

- Additive, no new contract: `F6-020` already serves all three statuses.
  Record the line under `## Open` in `tasks/CROSS_TRACK.md` against `F6-020` if
  it is not done yet, otherwise under `## Log`.

# Implementation notes

- Build the id from the schedule's home team link code, never from a name.
- Run order on a refresh: identity (only the first time) → games.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md`, `docs/validation/OFFLINE_DATABASE_PREPARATION.md`.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
