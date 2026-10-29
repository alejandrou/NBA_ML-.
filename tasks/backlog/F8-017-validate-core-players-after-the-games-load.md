---
id: F8-017
title: Validate core players after the games load
track: data
areas:
  - data-quality
  - testing
  - documentation
priority: 95
depends_on:
  - F8-005
read:
  - src/nba_data/validation/offline_database.py
  - src/nba_data/scraping/loaders/games.py
  - tests/unit/test_offline_database_validation.py
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/validation/GAME_DATASET_ACQUISITION.md
validation:
  - uv run pytest tests/unit/test_offline_database_validation.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba_f8006_tmp uv run nba-data validate offline-database --backfill-report reports/f8-003/nba-load/offline-backfill.json
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. Offline validator code and tests; the acceptance run reads the disposable nba_f8006_tmp only. Running the validator on nba belongs to F8-018.
---

# Goal

Let `validate offline-database` pass on a database that holds the games, so
F8-018's last step (the validator passing on `nba` after `backfill games`) can
be met.

# Evidence and current state

- `DEFAULT_PHASE_4D_TABLE_COUNTS` pins `core.players` at 2,654, the players
  with a cached player page (`validation/offline_database.py`).
- `backfill games` creates a `core.players` row for every box-score player with
  no player page, by design (F8-005): 39 for 2014-15 to 2025-26, with no
  `player_seasons`.
- On F8-006's disposable copy of `nba` (2026-10-28) the validator then exits 1
  with one issue: `core.players has 2693 rows; expected 2654`. Every other check
  passes.
- Checked read-only on `nba_f8006_tmp` (owner, 2026-10-29): `core.players` holds
  2,693 rows. 2,654 have a `core.player_seasons` row and 39 have none. All 39
  have `stats.player_game_totals` rows (1 to 82 each); none has played a second
  (inactive or did-not-play roster lines); none has a NULL Basketball Reference
  ID.
- Two of the 39 share a name with another player but have a different ID, and
  are different people: `smithch07`/`smithch05` (Chris Smith) and
  `thornma02`/`thornma01` (Marcus Thornton). `player_name` is not a key; the
  rule keys on the player row, not the name.

# Human decisions or resources

- [x] **Rule** (owner, 2026-10-29): *"Keep the pinned 2,654 for players that
      have a `player_season`. Each player without one must have at least one
      `stats.player_game_totals` row; a player with neither fails. Do not repin
      to 2,693."* Future seasons' games then need no repin.

# Acceptance criteria

- The pinned 2,654 counts only players with at least one `core.player_seasons`
  row.
- A player with no `player_season` and at least one `stats.player_game_totals`
  row passes; a player with neither fails the validator with an issue naming
  its Basketball Reference ID (fixture test). The number of such players is not
  pinned.
- Run against `nba_f8006_tmp` (2,693 players, 14,435 games), the validator
  exits 0 with no issue.
- Existing validator tests keep their meaning: an archive-only database (every
  player has a `player_season`) still passes at 2,654, and a different count
  of players with a `player_season` still fails.
- Offline tests only; the disposable run is the one documented check against a
  database.

# Scope

`src/nba_data/validation/offline_database.py`;
`tests/unit/test_offline_database_validation.py`;
`docs/validation/OFFLINE_DATABASE_PREPARATION.md` and
`docs/validation/GAME_DATASET_ACQUISITION.md` (what the pinned player count
covers).

# Out of scope

- Any loader, schema, or migration change.
- Running the validator against `nba` (F8-018).
- Repinning `core.players` to 2,693.

# Impact

- Validator only; no schema or loader change. The validator now reads
  `stats.player_game_totals` (existence per player).

# Cross-track impact

- None.

# Implementation notes

- Found by F8-006. Until this lands, the validation after `backfill games`
  reports exactly that one count issue.
- The SQLite fixture in `test_offline_database_validation.py` attaches only
  `core`; the new check needs a `stats` schema with a minimal
  `player_game_totals` table there.
- Before the disposable run, confirm the override selects the disposable
  database: the read-only `select current_database()` check in
  `GAME_DATASET_ACQUISITION.md` ("Rerunning it from the cache") must return
  `nba_f8006_tmp`; otherwise stop.

# Durable knowledge updates

- `OFFLINE_DATABASE_PREPARATION.md` — what the pinned player count covers and
  the rule for players created from box scores.
- `GAME_DATASET_ACQUISITION.md` — "Players created": the validator passes once
  this lands.

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
