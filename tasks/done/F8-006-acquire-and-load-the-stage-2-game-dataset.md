---
id: F8-006
title: Acquire and load the Stage 2 game dataset
track: data
areas:
  - scraping
  - data-quality
  - documentation
priority: 94
depends_on:
  - F8-003
  - F8-004
  - F8-005
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - docs/validation/MIGRATION_HEAD_HANDOVER.md
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/domain/BUSINESS_RULES.md
validation:
  - for f in tasks/manifests/F8-006-*.json; do uv run nba-data acquisition dry-run-game-season "$f"; done
  - DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba_f8006_tmp uv run nba-data backfill games --execute-approved-games-backfill --season 2015 --season 2016 --season 2017 --season 2018 --season 2019 --season 2020 --season 2021 --season 2022 --season 2023 --season 2024 --season 2025 --season 2026 --require-complete --output reports/f8-006/disposable/run1
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Live acquisition of the 12 season schedule pages and their 108 month pages (two runs, ~11 minutes) — the owner's direct instruction for each run.
  - Live acquisition of ~14,442 box scores, one approved season manifest at a time, in batches of `--max-fetches` (~25 hours in all) — the owner's direct instruction; given on 2026-10-25 for all twelve seasons (see "Run authorization").
---

# Goal

Build the game dataset the first predictor trains on: every regular-season game
and NBA Cup final from 2014-15 to 2025-26, cached, then loaded and reconciled on
a disposable database. The card ends at the disposable load; loading the
persistent `nba` database is F8-018 (owner, 2026-10-29: *"F8-006 ends at the
disposable load. The persistent steps move to F8-018."*).

# Evidence and current state

- The pilot measured 6.1-6.3 s per page, two requests per game with
  play-by-play (one without), ~55 KiB per box score, and no 429 in 84 requests
  (`PER_GAME_ACQUISITION_PILOT.md`, "Cost of Stage 2").
- Expected games: ten 1,230-game seasons, 1,059 in 2019-20, 1,080 in 2020-21,
  plus three Cup finals (2023-24 to 2025-26) — 14,442 box scores.
- F8-004 provides the planning and gated acquisition commands; F8-005 the
  loader and its per-season report; F8-003 season 2026 in `core`.

# Human decisions or resources

- [x] **Order**: schedules for all twelve seasons first (one season page run,
      then one month page run), then box scores newest season first, so the
      final test season (2025-26) and the seasons nearest it land earliest and a
      stopped acquisition still leaves the most useful data.
- [x] **Approval unit**: one season manifest. Each is committed to
      `tasks/manifests/` as `F8-006-<season>-box-scores-<yyyymmdd>.json` when the
      owner approves it, with the instruction quoted in `approval_basis`.
- [x] **Batch size**: `--max-fetches 550` (about an hour) unless the owner asks
      for another size; a batch is resumed by rerunning the same manifest.
- [x] **Run authorization** (owner, 2026-10-25): *"Do them yourself i give you
      permission as the owner of the project"*, in reply to the plan of season
      pages, month pages, then box scores season by season. It covers both
      schedule runs and every box-score batch of the twelve seasons, run back to
      back until each season reports `completed: true`; it does not cover the
      persistent-database steps. A 429 or failure still stops everything.
- [x] **Stopping between sessions**: every cached page is a safe point. A
      `reports/f8-006/STOP` file stops the batch driver before its next batch;
      killing a batch loses at most the page in flight, and `dry-run-game-season`
      shows what is left. Progress is appended to `reports/f8-006/progress.log`.
- [x] **A 429 or a failure stops the whole acquisition** until the owner decides;
      no retry loop.
- [x] **Split** (owner, 2026-10-29): *"F8-006 ends at the disposable load. The
      persistent steps move to F8-018."* The acceptance criterion on the
      persistent-database steps and their critical action moved there.
- [x] **Quarantines are not overridden.** A source error stays quarantined and is
      documented with its evidence; a loader defect stops this card and becomes
      a fix card for F8-005's code.

# Acceptance criteria

- Approved manifests for the schedule runs and the twelve box-score seasons are
  in `tasks/manifests/`, and each `dry-run-game-season` reports every URL as a
  cache hit.
- On a disposable database restored to the archive baseline (2000-2026),
  `backfill games` over the twelve seasons with `--require-complete`:
  - `missing_box_score` 0;
  - `loaded` equal to `expected` for every season, minus quarantines that are
    each documented as source errors;
  - `game_types` showing only `regular_season` and three `cup_final` (any other
    heading is listed and explained);
  - a rerun reports every game `unchanged`.
- `docs/validation/GAME_DATASET_ACQUISITION.md` records, per season: requests,
  bytes, wall time, games loaded, quarantines with evidence, warnings, players
  created, and neutral games, and the totals; plus the procedure to rerun it from
  the cache.

# Scope

`tasks/manifests/F8-006-*.json` (new, approved); `docs/validation/GAME_DATASET_ACQUISITION.md`; `docs/ml/PREDICTOR_PLAN.md` (Stage 2 result); and only documentation of
the runs. The loads run on a disposable database only. No product code: a
defect found here goes to a new card.

# Out of scope

- Play-by-play (Stage 4, F8-015), playoffs, play-in.
- Season 2026-27 (F8-008).
- Features and models (F8-007).
- Loading the persistent `nba` database and validating it (F8-018).

# Impact

- **Cache:** ~0.8 GB of box scores and ~6 MB of schedules under
  `data/raw/html/basketball-reference/`.
- **Database:** the disposable `nba_f8006_tmp` only — 14,435 games, 28,870
  team rows, 474,309 player rows, 39 players created (measured, in the record).
  `nba` is only read; F8-018 loads it.
- **API:** none; revision `0009` was already applied to `nba` (2026-10-24).

# Cross-track impact

- None.

# Implementation notes

- `SCRAPER_USER_AGENT` carries a real contact in the worktree's `.env` (set by
  the owner's instruction on 2026-10-18); `acquire-game-season` still refuses
  the placeholder, so a missing `.env` fails closed.
- The card stays in `active/` across many sessions. Park it between batches if
  the data slot is needed; a parked batch resumes from the cache.
- Keep reports under `reports/f8-006/` (never committed); the record quotes
  their totals.

# Durable knowledge updates

- `docs/validation/GAME_DATASET_ACQUISITION.md` — the Stage 2 acquisition and
  load record.
- `docs/ml/PREDICTOR_PLAN.md` — Stage 2 dataset result, dated.

# Review evidence

Live runs on 2026-10-25 to 2026-10-28 under the owner's instruction (see "Run
authorization"); loads on the disposable `nba_f8006_tmp`, a `pg_dump` copy of
`nba`. `nba` was only read. Full record: `docs/validation/GAME_DATASET_ACQUISITION.md`.

## Automated validation

- Command: `for f in tasks/manifests/F8-006-*.json; do uv run nba-data acquisition dry-run-game-season "$f"; done`
- Result: all 30 manifests (6 season-page, 12 month-page, and 12 box-score manifests) report every URL as a cache hit: 14,442 box scores and 114 schedule URLs (6 season pages plus 108 month pages).
- Command: `DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba_f8006_tmp uv run nba-data backfill games --execute-approved-games-backfill --season 2015 … --season 2026 --require-complete --output reports/f8-006/disposable/run1` (then `run2`)
- Result: exit 1, caused only by the 7 quarantines. `missing_box_score` 0 in every season; `loaded` equals `expected` minus the quarantines in every season. `game_types` shows `regular_season` and 3 `cup_final`, nothing else. 14,435 games, 28,870 team rows, 474,309 player rows, 39 players created. The rerun reports all 14,435 games `unchanged`, 0 players created, 0 neutral-site updates.
- Command: `DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba_f8006_tmp uv run nba-data validate offline-database --backfill-report reports/f8-003/nba-load/offline-backfill.json`
- Result: exit 1 with one issue only, `core.players has 2693 rows; expected 2654`. The 39 players created from box scores are intended (F8-005); the fix is F8-017.
- Command: `uv run pytest`
- Result: 1470 passed, 254 skipped (fresh final review, 2026-10-29). PostgreSQL integration tests were skipped without disposable-test opt-in; the recorded full disposable loads were checked against their reports.
- Command: `uv run python scripts/validate_tasks.py` and `--all-worktrees`
- Result: passed in the final review, including after moving this card to `done/`.
- Command: `uv run ruff check .` and `uv run mypy src/nba_data`
- Result: both passed; mypy checked 94 source files.
- Independent offline recheck (2026-10-29): all 30 manifest approval contracts validated; all 14,442 box-score URLs and 114 schedule URLs are unique cache hits; each box-score manifest exactly matches the current offline selection. Reconciled all 24 per-season load/rerun reports: 7 documented quarantines, no missing or failed games, 14,435 loaded then unchanged, and no new players or neutral-site updates on the rerun. No live acquisition or database writes were run during this final review.

## Manual happy path

1. Run the dry-run loop above. It makes no request.
2. Open `reports/f8-006/disposable/run2/NBA_2026_games-backfill.json`.
3. Query the disposable database `nba_f8006_tmp` (never `nba`, which holds no
   games yet): `select count(*) from core.games` (14,435).

Expected result: every manifest reports `missing_cache_entries` 0, and the
2025-26 report shows 1,231 `unchanged`, 1 `cup_final`, and 8 neutral games.

## Manual sad path

1. Inspect a quarantined game in its report, e.g. `201712040NOP` in
   `reports/f8-006/disposable/run1/NBA_2018_games-backfill.json`.
2. Confirm it is not in `core.games` on `nba_f8006_tmp`.
3. Rerun `backfill games --execute-approved-games-backfill --season 2018 --require-complete --output reports/f8-006/disposable/review-2018` on the disposable database, with
   `DATABASE_URL` set to `nba_f8006_tmp` and the `current_database()` check
   from `GAME_DATASET_ACQUISITION.md` ("Rerunning it from the cache") passing
   first.

Expected result: the game is quarantined `minutes_mismatch` (GSW players sum to
241:24 against a 240-minute game) on both runs, and no row exists for it.

## Known limitations

- **`nba` holds no games yet.** Loading it is F8-018 (`backfill games` and
  `validate offline-database`, from merged `origin/main` on the owner's
  instruction), which depends on F8-016 and F8-017.
- Seven games stay quarantined as source errors (`GAME_DATASET_ACQUISITION.md`,
  "Quarantines"). F8-011 records what their absence does to rest days,
  back-to-backs, seven-day counts, and Elo.
- In 2016-17, 2017-18, 2022-23, and 2023-24, `neutral_site` is `NULL` for every
  game, because inference waits for a fully loaded season. 17 neutral games are
  unflagged (listed in F8-016, which fixes it); F8-011 would count them as home
  games.
- On the disposable copy, `validate offline-database` reports
  `core.players has 2693 rows; expected 2654` until F8-017 lands.
- Three batches were killed in flight and wrote no report. Their figures come
  from cache metadata.
- Keep the disposable database `nba_f8006_tmp` for F8-016 and F8-017
  acceptance checks after this review closes. Clean it up only after both
  follow-up checks are complete and the owner authorizes removal.
