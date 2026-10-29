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
