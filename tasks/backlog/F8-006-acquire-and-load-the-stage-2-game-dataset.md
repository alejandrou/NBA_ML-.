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
  - uv run nba-data backfill games --execute-approved-games-backfill --season 2015 --season 2016 --season 2017 --season 2018 --season 2019 --season 2020 --season 2021 --season 2022 --season 2023 --season 2024 --season 2025 --season 2026 --require-complete --output reports/f8-006/games
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Live acquisition of the 12 season schedule pages and their ~96 month pages (two runs, ~11 minutes) — the owner's direct instruction for each run.
  - Live acquisition of ~14,442 box scores, one approved season manifest at a time, in batches of `--max-fetches` (~25 hours in all) — the owner's direct instruction for each batch.
  - Applying F8-002's revision to the persistent nba database and running `backfill games` against it — from merged origin/main only, each with the owner's approval. Season 2026 is already loaded there (F8-003, 2026-10-24).
---

# Goal

Build the game dataset the first predictor trains on: every regular-season game
and NBA Cup final from 2014-15 to 2025-26, cached, loaded, and reconciled, first
on a disposable database and then, with approval, in `nba`.

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
- [x] **A 429 or a failure stops the whole acquisition** until the owner decides;
      no retry loop.
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
- The persistent-database steps are recorded in the order they ran, each with
  the owner's instruction: revision applied (`MIGRATION_HEAD_HANDOVER.md`),
  `backfill games` run, and `validate offline-database` passing afterwards.
  Season 2026 was loaded into `nba` by F8-003 on 2026-10-24
  (`OFFLINE_DATABASE_PREPARATION.md`).

# Scope

`tasks/manifests/F8-006-*.json` (new, approved); `docs/validation/GAME_DATASET_ACQUISITION.md`
(new); `docs/ml/PREDICTOR_PLAN.md` (Stage 2 result); and only documentation of
the runs. No product code: a defect found here goes to a new card.

# Out of scope

- Play-by-play (Stage 4, F8-015), playoffs, play-in.
- Season 2026-27 (F8-008).
- Features and models (F8-007).

# Impact

- **Cache:** ~0.8 GB of box scores and ~6 MB of schedules under
  `data/raw/html/basketball-reference/`.
- **Database:** about 14,442 games, 28,884 team rows, and ~460,000 player rows (about 32 lines a game in the pilot)
  (measured, not estimated, in the record).
- **API:** the readiness contract (ADR 0018) — the `app` worktree answers 503
  after the revision is applied until its next task starts from the new
  `origin/main`.

# Cross-track impact

- None new. The handoff for the game tables is F8-002's.

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
