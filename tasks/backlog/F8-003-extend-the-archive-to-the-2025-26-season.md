---
id: F8-003
title: Extend the archive to the 2025-26 season
track: data
areas:
  - scraping
  - data-quality
  - testing
  - documentation
priority: 100
depends_on: []
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md
  - docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - src/nba_data/scraping/nba_team_season_manifest.py
  - src/nba_data/scraping/nba_team_season_acquisition.py
  - src/nba_data/scraping/player_page_acquisition.py
  - src/nba_data/validation/offline_database.py
  - src/nba_data/cli/main.py
validation:
  - uv run pytest tests/unit/test_nba_team_season_manifest.py tests/unit/test_nba_team_season_acquisition.py tests/unit/test_offline_database_validation.py tests/unit/test_game_pilot_validation.py tests/unit/test_player_page_acquisition.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Live acquisition of the 30 team-season pages for season 2026 (`acquire-nba-team-seasons 2026 2026`, ~3 minutes) — the owner's direct instruction for that run.
  - Live acquisition of the player pages of 2025-26 players with no cached page (`acquire-player-pages --start-year 2026 --end-year 2026`, cache-first; the dry run gives the exact count before asking) — a second direct instruction.
  - Loading season 2026 into the persistent nba database — only from merged origin/main and with the owner's approval; F8-006 may combine it with the Stage 2 load. Everything in review runs on a disposable database.
---

# Goal

Bring season 2025-26 (end year 2026) into the archive through the same
team-season and player-page path as 2000-2025: `core.seasons`,
`core.team_seasons`, rosters, team-season statistics, and player-page
statistics. It is the last complete season, Stage 3's final test season, and
the season every Stage 2 2025-26 game row needs a team-season for.

# Evidence and current state

- The team-season manifest is pinned to 2000-2025:
  `SEASON_END_YEAR = 2025`, `MANIFEST_ID = "nba-team-season-2000-2025"`,
  `EXPECTED_MANIFEST_URLS = 775`
  (`src/nba_data/scraping/nba_team_season_manifest.py:9-12`), and
  `validate_nba_team_season_year_range` refuses later years
  (`nba_team_season_acquisition.py:150-160`).
- The offline database validator expects 26 seasons, 775 team-seasons and
  aliases, and fixed player and backfill counts
  (`src/nba_data/validation/offline_database.py:22-50`).
- `validate game-pilot` passes `archive_last_season=SEASON_END_YEAR`
  (`cli/main.py:729`), so 2025-26 pilot games are treated as beyond the archive
  (pilot finding 10).
- The 2,551 cached player pages were all fetched on 2026-07-05, after the
  2025-26 Finals, so their 2025-26 rows are complete. The player-page producers
  scope by `core.seasons` (`scraping/player_page_scope.py`), so those rows move
  from out-of-scope to in-scope once 2026 is loaded; today they are part of the
  19,692 / 20,280 out-of-scope counts (`OFFLINE_DATABASE_PREPARATION.md:220-235`).
- Players new in 2025-26 have no cached page. `acquire-player-pages` builds its
  list from `core.player_seasons` with `--start-year`/`--end-year` and is
  cache-first, so after the 2026 rosters are loaded it fetches only those.
- The 2025-26 franchise codes are the 2024-25 ones; `_active_teams_for_season`
  needs no new branch.

# Human decisions or resources

- [x] **Season 2025-26 only.** It is complete, so its pages are final and the
      never-overwrite cache is correct for it. 2026-27 is in progress; its pages
      change daily, and fetching them into a never-overwrite cache would freeze a
      partial season. That is the current-season card's problem (F8-008), not
      this one.
- [x] **Same path as the archive, no shortcut from box scores.** Team-seasons
      and players come from team and player pages; box scores never create a
      team-season.
- [x] **Player-page statistics for 2025-26 load too**, from the cached pages plus
      the newcomers' pages. A season with identity but no player statistics would
      be a hole the coverage oracle reports, and the cost is small.
- [x] **Live runs**: `SCRAPER_USER_AGENT` carries a real contact in the
      worktree's `.env` (set by the owner's instruction on 2026-10-18). The
      existing commands only refuse a blank value, so confirm it before each
      run: `uv run python -c "from nba_data.config.settings import Settings;
      print(Settings().scraper_user_agent)"`.

# Acceptance criteria

- The team-season manifest covers 2000-2026: `SEASON_END_YEAR = 2026`,
  `MANIFEST_ID = "nba-team-season-2000-2026"`, `EXPECTED_MANIFEST_URLS = 805`;
  `acquire-nba-team-seasons 2026 2026` plans exactly the 30 season-2026 URLs and
  `dry-run-nba-team-seasons` reports 775 hits and 30 missing before the run.
- The acquisition guards are unchanged apart from the year bound: same flags,
  same pace ceiling, same refusal messages, and their tests still pass.
- After the two live runs, on a **disposable** database, the documented rebuild
  order (`backfill offline`, `backfill stats`, `backfill player-stats`,
  `backfill player-postseason-stats`, `validate build-stats-coverage`,
  `validate official-stats`) completes with zero failed entries, zero failed
  rows, and zero in-scope unresolved rows.
- `OfflineDatabaseValidationExpectations` holds the counts measured on that
  rebuild (27 seasons, 805 team-seasons and aliases, and the measured player,
  roster, and backfill row counts), and `validate offline-database` passes
  against it. The out-of-scope counts, now without 2026, are recorded in
  `OFFLINE_DATABASE_PREPARATION.md`.
- `validate game-pilot` uses the new last season. Rerun over the pilot cache, it
  still reports `200010310ATL` as the only source-error failure, or every new
  difference is explained in the pilot record.
- No change to parsers, loaders, or schema.

# Scope

`scraping/nba_team_season_manifest.py`, `nba_team_season_acquisition.py` (the
year bound only), `validation/offline_database.py`, `cli/main.py` (only if a
constant moves), their unit tests, and
`docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md`,
`PLAYER_PAGE_CACHE_ACQUISITION.md`, `OFFLINE_DATABASE_PREPARATION.md`,
`PER_GAME_ACQUISITION_PILOT.md`.

# Out of scope

- Season 2026-27 and any refresh of an already-cached page (F8-008).
- Seasons before 2000.
- Games, box scores, and the game tables (F8-002, F8-005).
- Moving the two older acquisition modules onto `scraping/cache_writer.py`.

# Impact

- **Data:** 30 team-season pages and the 2025-26 newcomers' player pages join
  the cache; a rebuilt archive gains season 2026.
- **Validation:** the pinned offline-database counts move to the measured
  2000-2026 values.
- **API:** `GET /api/v1/seasons` and the team and player routes start returning
  2025-26 once the persistent database is loaded — new rows, no contract change.

# Cross-track impact

- None. New rows in existing tables under an unchanged contract; the `app`
  track's routes serve them without change.

# Implementation notes

- Order: code and tests → dry run → live team pages (instruction 1) → load
  into a disposable database → player-page dry run against it → live player
  pages (instruction 2) → full rebuild on a fresh disposable database → pin the
  measured counts → docs.
- Point `DATABASE_URL` at the disposable database for the player-page dry run
  and acquisition, so the manifest is built from the 2026 rosters without
  touching `nba`.
- A run stops at its first failure; the rerun costs only the gap (cache-first).
- Both older acquisition modules still check-then-replace in their private cache
  writers: run one acquisition process at a time.

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — the 2000-2026 baseline and
  its counts.
- `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md` and
  `PLAYER_PAGE_CACHE_ACQUISITION.md` — the 2026 runs.

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
