---
id: F8-018
title: Load the Stage 2 game dataset into nba
track: data
areas:
  - scraping
  - data-quality
  - documentation
priority: 89
depends_on:
  - F8-006
  - F8-016
  - F8-017
read:
  - docs/validation/GAME_DATASET_ACQUISITION.md
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/validation/MIGRATION_HEAD_HANDOVER.md
  - docs/ml/PREDICTOR_PLAN.md
validation:
  - uv run python -c "from sqlalchemy import text; from nba_data.db.session import create_db_engine; print(create_db_engine().connect().execute(text('select current_database()')).scalar_one())"
  - uv run nba-data backfill games --execute-approved-games-backfill --season 2015 --season 2016 --season 2017 --season 2018 --season 2019 --season 2020 --season 2021 --season 2022 --season 2023 --season 2024 --season 2025 --season 2026 --require-complete --output reports/f8-018/nba-load
  - uv run nba-data backfill games --execute-approved-games-backfill --season 2015 --season 2016 --season 2017 --season 2018 --season 2019 --season 2020 --season 2021 --season 2022 --season 2023 --season 2024 --season 2025 --season 2026 --require-complete --output reports/f8-018/nba-rerun
  - uv run nba-data validate offline-database --backfill-report reports/f8-003/nba-load/offline-backfill.json
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Running `backfill games` for 2015–2026 against the persistent nba database, and its rerun — from merged origin/main only, on the owner's explicit instruction naming the run.
  - Running `validate offline-database` against nba afterwards (read-only) — from merged origin/main, on the owner's explicit instruction.
---

# Goal

Load the Stage 2 game dataset that F8-006 acquired and proved on a disposable
database into the persistent `nba` database, with every neutral site decided
and the offline validator passing, so F8-007, F8-008, and the games routes read
real games.

# Evidence and current state

- F8-006 cached all 14,442 selected box scores of 2014-15 to 2025-26 and loaded
  them into the disposable `nba_f8006_tmp` (2026-10-28): 14,435 games, 28,870
  team rows, 474,309 player rows, 39 players created; 7 games quarantined as
  source errors; a rerun fully `unchanged` (`GAME_DATASET_ACQUISITION.md`).
- Revision `0009_games_and_box_scores` is already applied to `nba` (2026-10-24,
  `MIGRATION_HEAD_HANDOVER.md`); its game tables are empty. This card applies no
  migration.
- F8-016 decides `neutral_site` in the four seasons with a quarantine; F8-017
  lets the validator accept the 39 players created from box scores. Both must be
  merged first.
- After F8-016, the twelve seasons hold 131 neutral games (2, 2, 3, 3, 3, 91, 0,
  0, 4, 7, 8, 8 from 2014-15 to 2025-26).

# Human decisions or resources

- [x] **Split from F8-006** (owner, 2026-10-29): *"F8-006 ends at the disposable
      load. The persistent steps move to F8-018."*
- [x] **Run authorization**: each step runs from merged `origin/main` on the
      owner's explicit instruction. This card records the steps; it authorizes
      none of them.

# Acceptance criteria

- Before any write, the configured connection's `select current_database()`
  returns `nba`, and the game tables are empty (counts recorded).
- `backfill games` for seasons 2015–2026 against `nba` with
  `--require-complete --output reports/f8-018/nba-load`:
  - its non-zero exit comes only from the 7 documented quarantines
    (`missing_box_score` 0 and nothing in `failed` in every season);
  - `nba` then holds 14,435 games, 28,870 team rows, and 474,309 player rows,
    with 39 players created;
  - no game has a NULL `neutral_site`.
- A rerun reports every game `unchanged`, 0 players created, and 0 neutral-site
  updates.
- `validate offline-database` passes on `nba` afterwards.
- `GAME_DATASET_ACQUISITION.md`, "Persistent database", records each step in
  the order it ran, with the date, the owner's instruction, and the figures.

# Scope

The runs above and their documentation: `docs/validation/GAME_DATASET_ACQUISITION.md`
and the Stage 2 result in `docs/ml/PREDICTOR_PLAN.md`. No product code: a defect
found here stops the card and goes to a new one.

# Out of scope

- Any migration (`0009` is already applied).
- Any live request: every page comes from the cache.
- Overriding a quarantine, or any change to the loader or validator (F8-016 and
  F8-017 own those).
- Season 2026-27 (F8-008).

# Impact

- **Database:** `nba` gains 14,435 games, 28,870 team rows, 474,309 player
  rows, and 39 players.
- **API:** no readiness change; the tables already exist. The games routes
  (F6-020) serve real games once this lands.

# Cross-track impact

- None.

# Implementation notes

- The commands rely on the normal configuration selecting `nba`. Run the
  `current_database()` check first in the same shell; stop unless it returns
  `nba`. Never run them with a `DATABASE_URL` override left from a disposable
  run.
- The validator command reuses F8-003's archive backfill report, as F8-006 did
  on the disposable copy.
- Keep reports under `reports/f8-018/` (never committed); the record quotes
  their totals.

# Durable knowledge updates

- `docs/validation/GAME_DATASET_ACQUISITION.md` — "Persistent database": the
  run, dated, with the owner's instruction.
- `docs/ml/PREDICTOR_PLAN.md` — the Stage 2 result: loaded into `nba`.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.

Expected result:

## Manual sad path

1.

Expected result:

## Known limitations

- None.
