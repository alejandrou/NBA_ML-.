---
id: F8-016
title: Infer neutral sites in seasons with quarantined games
track: data
areas:
  - scraping
  - data-quality
  - testing
  - documentation
priority: 90
depends_on:
  - F8-005
read:
  - src/nba_data/scraping/loaders/games.py
  - src/nba_data/scraping/offline_games_backfill.py
  - tests/unit/test_game_loader.py
  - tests/unit/test_offline_games_backfill.py
  - docs/validation/GAME_DATASET_ACQUISITION.md
  - docs/domain/BUSINESS_RULES.md
validation:
  - uv run pytest tests/unit/test_offline_games_backfill.py tests/unit/test_game_loader.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba_f8006_tmp uv run nba-data backfill games --execute-approved-games-backfill --season 2015 --season 2016 --season 2017 --season 2018 --season 2019 --season 2020 --season 2021 --season 2022 --season 2023 --season 2024 --season 2025 --season 2026 --require-complete --output reports/f8-016/disposable
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None.
---

# Goal

Give every loaded game of a season a `neutral_site` decision even when some of
the season's games are permanently quarantined as source errors.

# Evidence and current state

- `derive_neutral_sites` (`scraping/loaders/games.py`) changes no flag unless
  every selected game of the season is loaded (`expected_game_ids` a subset of
  the loaded ids), and otherwise reports `neutral_site_deferred`.
  `_backfill_season` (`scraping/offline_games_backfill.py`) knows which games
  it quarantined, which had no box score, and which failed, but passes only the
  selected ids.
- F8-006's disposable load (2026-10-28) quarantined seven games as source errors
  (player minutes or turnovers that do not sum to the team totals on the page):
  one in 2016-17, three in 2017-18, two in 2022-23, one in 2023-24. Those four
  seasons' 4,914 loaded games all keep `neutral_site = NULL`
  (`GAME_DATASET_ACQUISITION.md`). Every other game of `core.games` (14,435 in
  all) has a value.
- Checked read-only on `nba_f8006_tmp` (owner, 2026-10-29): running the
  existing `neutral_sites()` rule over the four NULL seasons decides every game
  (0 undetermined, no warnings) and flags 17:
  - 2016-17: `201701120DEN` London; `201701120PHO`, `201701140PHO` Mexico City.
  - 2017-18: `201712070BRK`, `201712090BRK` Mexico City; `201801110PHI` London.
  - 2022-23: `202212170SAS` Mexico City; `202301190DET` Paris; `202304060SAS`,
    `202304080SAS` Austin.
  - 2023-24: `202311090ORL` Mexico City; `202312070LAL`, `202312070MIL` (Cup
    semifinals) and `202312090LAL` (Cup final) Las Vegas; `202401110CLE` Paris;
    `202403150SAS`, `202403170SAS` Austin.
- F8-011 counts `NULL` as a home game, so until this lands those 17 games get
  home advantage in Elo and the features.

# Human decisions or resources

- [x] **Rule** (owner, 2026-10-29): *"Run inference over the loaded games when
      every selected game that is not loaded was quarantined in the same run.
      Keep deferring when any box score is missing."* One quarantined game
      changes no team's most common home city.
- [x] **Austin** (owner, 2026-10-29): *"Keep the city rule unchanged, so the
      Spurs' Austin games stay neutral (8 games, 2023 to 2026). No hard-coded
      exceptions."*

# Acceptance criteria

- A season whose only unloaded selected games were quarantined in the same run
  gets the same inference as a fully loaded season (venue city differs from the
  home team's most common home city).
- A season with any selected game missing its box score still defers with
  `neutral_site_deferred` and changes no flag; so does a season with a game
  that failed to load (an exception is not a quarantine).
- Offline fixture tests for both cases, and for a rerun being a no-op.
- A rerun of `backfill games` on `nba_f8006_tmp` (the validation command above,
  after the `current_database()` check) flags exactly the 17 games listed above
  in 2016-17, 2017-18, 2022-23, and 2023-24, reports `neutral_site_updates` 0 in
  the other eight seasons and leaves their flags unchanged, and leaves no NULL
  `neutral_site` in any of the twelve seasons
  (`select count(*) from core.games where neutral_site is null` returns 0). Its
  only non-zero exit cause remains the 7 quarantines.

# Scope

`src/nba_data/scraping/loaders/games.py` (`derive_neutral_sites`);
`src/nba_data/scraping/offline_games_backfill.py` (what it passes);
`tests/unit/test_game_loader.py`, `tests/unit/test_offline_games_backfill.py`;
`docs/validation/GAME_DATASET_ACQUISITION.md`;
`docs/architecture/SYSTEM_DESIGN.md` (the deferral sentence).

# Out of scope

- The city rule itself, and any hard-coded venue exception (Austin stays
  neutral).
- Loading the games into `nba`, or rerunning the backfill there (F8-018).
- The 7 quarantines; they stay out of `core.games`.

# Impact

- Loader behaviour only; no schema change. A rerun of `backfill games` sets the
  flags (`derive_neutral_sites` updates only values that change).

# Cross-track impact

- None.

# Implementation notes

- Found by F8-006; recorded there as a known limitation.
- The disposable rerun writes only to `nba_f8006_tmp`. Before it, run the
  read-only `select current_database()` check from `GAME_DATASET_ACQUISITION.md`
  ("Rerunning it from the cache") and stop unless it returns `nba_f8006_tmp`.

# Durable knowledge updates

- `GAME_DATASET_ACQUISITION.md` — neutral games of the four seasons after the
  rerun, and the per-season table's *Neutral* column.
- `SYSTEM_DESIGN.md` — inference waits for every selected game except those
  quarantined in the same run.

# Review evidence

## Automated validation

- `uv run pytest tests/unit/test_offline_games_backfill.py tests/unit/test_game_loader.py` — 94 passed.
- `uv run ruff check .` — all checks passed.
- `uv run mypy src/nba_data` — no issues in 99 source files.
- `uv run pytest` — 1591 passed, 257 skipped.
- `uv run python scripts/validate_tasks.py` (and `--all-worktrees`) — passed.
- Mutation check: with `unloaded_game_ids` removed from the backfill call, the
  missing-box-score and failed-load rerun tests fail (2 failed); restored.
- Disposable rerun on `nba_f8006_tmp` (`select current_database()` checked first,
  returned `nba_f8006_tmp`). Before: 4,914 NULL `neutral_site`, all in 2017, 2018,
  2023, 2024.
  - Run A (`reports/f8-016/disposable`), exit 1: 14,435 unchanged, 7 quarantined,
    0 missing, 0 failed. `neutral_site_updates` 1,229 / 1,227 / 1,228 / 1,230 in
    2016-17 / 2017-18 / 2022-23 / 2023-24, 0 in the other eight; no
    `neutral_site_deferred`. Flagged exactly the 17 listed games. Afterwards
    `select count(*) from core.games where neutral_site is null` = 0; 131 neutral
    games across the twelve seasons. Only failure cause: the 7 quarantines.
  - Run B (`reports/f8-016/disposable-rerun`), on the final code after the review
    fix, exit 1: same counts, `neutral_site_updates` 0 in every season, same
    neutral lists, 0 NULL.
  - Run A ran before the review fix (unloaded games defer). That fix only
    matters when a run has missing or failed games, and Run A had none; Run B
    confirms the final code changes nothing.
- Independent review (2026-10-31): repeated the 94 focused tests, full suite
  (1,591 passed, 257 skipped), Ruff, mypy, and both task validators; all passed.
  Followed the manual sad path: 4 passed, 20 deselected.
- Independent manual happy path (`reports/f8-016/manual-review-20261031`):
  checked `current_database()` through the configured connection before the
  twelve-season cache-only backfill; returned `nba_f8006_tmp`. Exit 1, solely
  the exact 7 documented quarantines; 14,435 unchanged, 0 loaded, 0 missing,
  0 failed, 0 neutral-site updates in every season, no deferral warning.
  Asserted the exact 17 neutral game IDs in the four quarantine seasons and
  compared every game's flag against a pre-run snapshot: all 14,435 unchanged.
  Final SQL NULL count was 0; the database still held 131 neutral games.

## Manual happy path

1. Point `DATABASE_URL` at `nba_f8006_tmp` (after the `current_database()` check in
   `GAME_DATASET_ACQUISITION.md`, "Rerunning it from the cache") and rerun the
   card's `backfill games` command to a new `--output` directory.
2. Run `select count(*) from core.games where neutral_site is null`.

Expected result: exit 1, caused only by the 7 quarantines; `neutral_site_updates` 0
in every season (already set); the four quarantine seasons list the 17 games in
`neutral_games`; the query returns 0.

## Manual sad path

1. `uv run pytest tests/unit/test_offline_games_backfill.py -k "defers or earlier_runs"`.

Expected result: 4 passed (including the partial-season test). A rerun with a
missing box score, a failed load, or an earlier run's quarantine that is now a
missing box score reports
`neutral_site_deferred` and leaves every existing True/False flag unchanged, even
when an earlier run stored the affected game; a previous quarantine does not
excuse a box score missing in the current run.

## Known limitations

- `nba` is unchanged; its games and flags are loaded by F8-018.
- Called directly without `expected_game_ids`, `derive_neutral_sites` still infers
  over whatever rows exist. Only the backfill passes the run's outcome.
