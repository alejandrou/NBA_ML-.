---
id: F8-008
title: Keep the current season current
track: data
areas:
  - scraping
  - data-quality
  - documentation
priority: 87
depends_on:
  - F8-006
  - F8-013
  - F8-014
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/validation/CURRENT_SEASON_REFRESH.md
  - docs/validation/MIGRATION_HEAD_HANDOVER.md
  - docs/decisions/0022-version-snapshots-of-pages-that-still-change.md
  - docs/domain/BUSINESS_RULES.md
validation:
  - uv run nba-data acquisition dry-run-current-season tasks/manifests/F8-008-current-season-2027.json --as-of 2026-11-01
  - uv run nba-data backfill current-season-identity --season 2027
  - uv run nba-data backfill current-season-games --season 2027 --as-of 2026-11-01 --output reports/f8-008/current-season.json
  - uv run nba-data validate offline-database
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Approving the standing `current_season_refresh` manifest for season 2027 — the owner's decision, recorded in the manifest.
  - The first live refresh (`acquire-current-season`, ~60 requests including the 30 team pages, ~6 minutes) and every later one — the owner's direct instruction for each run.
  - Loading season 2027 into the persistent nba database — from merged origin/main only, with the owner's approval.
---

# Goal

Bring season 2026-27 into the database and keep it current: run the first
refresh, load it on a disposable database and then in `nba`, measure it, and
leave a one-instruction procedure for every later refresh. Stage 5's
"OKC vs Chicago tonight" needs it.

# Evidence and current state

- F8-012 versions mutable pages as snapshots; F8-013 gives the gated
  `acquire-current-season` with a standing, bounded manifest; F8-014 loads
  identity, scheduled, final, and postponed games.
- F8-006 has applied F8-002's revision to `nba` and loaded 2014-15 to 2025-26.
- The 2026-27 regular season starts in late October 2026.
- Every live run needs the owner's direct, current instruction (`AGENTS.md`).

# Human decisions or resources

- [x] **Refresh cadence and approval** (decided 2026-10-18): manual, one owner
      instruction per refresh, no scheduler. Measure the first runs; a standing
      approval would be a separate `shared` card if ever wanted.
- [x] **Changing pages**: versioned snapshots (F8-012, ADR 0022).
- [x] **Current-season identity**: team pages, identity only (F8-014).
- [x] **Split**: F8-012 (snapshots) → F8-013 (refresh command) → F8-014
      (loaders) → this card (first run and the procedure).

# Acceptance criteria

- The owner approves `tasks/manifests/F8-008-current-season-2027.json`
  (drafted by `F8-013`'s command), and the dry run for the chosen `as-of` shows
  the plan before the first live run.
- First refresh, on the owner's instruction: the report shows no failure and no
  429; snapshots of the season page, its month pages, and 30 team pages exist;
  box scores of every scored game exist in the archive cache.
- On a disposable database restored from `nba`: identity loads 30
  team-seasons; games load with every schedule row present once; counts per
  status match the snapshot; `validate offline-database` passes; a second load
  writes nothing.
- With the owner's approval, the same load in `nba` from merged `origin/main`.
- `docs/validation/CURRENT_SEASON_REFRESH.md` records the measured requests,
  bytes, and wall time, and the exact instruction and commands for the next
  refresh ("Refresh the current season as of YYYY-MM-DD.").

# Scope

`tasks/manifests/F8-008-current-season-2027.json`,
`docs/validation/CURRENT_SEASON_REFRESH.md`, `docs/ml/PREDICTOR_PLAN.md`
(Stage 5 data path). No code; a defect found here goes back to F8-013 or F8-014
as a new card.

# Out of scope

Predictions (F8-010). Any season other than 2027. Changing the gate.

# Impact

- `nba` gains season 2027 and its games.

# Cross-track impact

- Additive: new rows in `core.games` under F6-020's unchanged contract.
  F8-014 records the `CROSS_TRACK.md` line.

# Implementation notes

- Use the `as-of` date of the run day; the owner's instruction names it.
- The validation commands above use 2026-11-01 as a placeholder: replace it
  with the run's `as-of` date in the review evidence.

# Durable knowledge updates

- `docs/validation/CURRENT_SEASON_REFRESH.md` and `docs/ml/PREDICTOR_PLAN.md`.

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
