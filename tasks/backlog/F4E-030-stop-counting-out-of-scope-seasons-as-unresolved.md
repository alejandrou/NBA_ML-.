---
id: F4E-030
title: Stop counting out-of-scope seasons as unresolved in the player-page backfills
areas:
  - scraping
  - testing
priority: 55
depends_on:
  - F4E-022
read:
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/offline_player_postseason_stats_backfill.py
  - src/nba_data/cli/main.py
  - scripts/dev/rehearse_player_page_rebuild.py
validation:
  - uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make a complete, fully successful player-page backfill exit 0. Today both
producers exit 1 on a perfect run because they count rows for seasons the archive
deliberately does not load as "unresolved", which is indistinguishable in the
report from a genuine data gap.

# Evidence and current state

On the `F4E-024` rebuild — 0 failed entries, 0 failed rows, every expected row
loaded — both producers still exited 1:

| Producer | Field | Value | `entries_failed` | `rows_failed` |
|---|---|---|---|---|
| `backfill player-stats` | `unresolved_players_or_seasons` | 19,692 | 0 | 0 |
| `backfill player-postseason-stats` | `unresolved_players_or_seasons_or_team_stints` | 20,280 | 0 | 0 |

Those counts equal the coverage artifact's out-of-scope expectations **exactly**
(19,692 regular; 10,140 + 10,140 postseason). Every sampled case is a pre-2000
season.

The mechanism:

- `offline_player_stats_backfill.py:231-234` counts a row as unresolved whenever
  the loader's reason is one of `missing_player`, `missing_season`,
  `missing_player_season`, and `:144` sums that across entries into the report
  field. `offline_player_postseason_stats_backfill.py:235-238` and `:149` do the
  same.
- `src/nba_data/cli/main.py:460` and `:536` list those fields in
  `failure_fields`, so a nonzero value alone drives `typer.Exit(code=1)` via the
  helper at `:861-866`.
- Cached player pages cover 1983–2026; the archive loads 2000–2025 only
  (`nba_team_season_manifest.py:10-12`). Every pre-2000 row therefore resolves to
  `missing_season` — correctly, since that season is not in `core.seasons` — and
  is then counted as a failure signal.

Two concrete costs. First, the producers' exit codes carry no information on a
complete run: an operator cannot distinguish "everything loaded" from "something
is genuinely unresolvable" without opening the JSON and doing arithmetic.
Second, `scripts/dev/rehearse_player_page_rebuild.py` already carries a
workaround — `_is_out_of_scope_only()` continues past a nonzero exit when the
sole failure signal is that counter and both real failure counters are zero.
That helper exists only because of this defect and should not outlive it.

# Human decisions or resources

- [x] Which season range decides "out of scope" — the archive's 2000–2025,
  settled in code at `nba_team_season_manifest.py:10-12` and asserted by
  `validate offline-database`. This card reports against it rather than changing
  it.

# Acceptance criteria

- Both producers distinguish **out of scope** from **unresolved**. A row whose
  season year is outside the seasons present in `core.seasons` is counted in a
  new, separately named report field; a row that is in range but still cannot be
  resolved stays in `unresolved_players_or_seasons` /
  `unresolved_players_or_seasons_or_team_stints`.
- The season-range check is made **before** the loader reason is consulted, so an
  out-of-scope row is classified by its season regardless of whether it surfaced
  as `missing_season`, `missing_player`, or `missing_player_season` — a player
  who only ever appeared before 2000 is out of scope, not missing.
- On the `F4E-024` rebuild state, both producers report the in-range unresolved
  counters as **0**, report the out-of-scope counters as 19,692 and 20,280, and
  **exit 0**.
- An in-range unresolved row still fails the run. A unit test supplies a row for
  a season inside the range whose player is absent and asserts a nonzero
  in-range counter and a nonzero exit code.
- The new field is added to `failure_fields` **only if** it should fail the run —
  it should not. `src/nba_data/cli/main.py` keeps the in-range counters in
  `failure_fields` and leaves the out-of-scope counters out, and a CLI test
  covers both directions.
- Both report `to_dict()` shapes gain the new key. Existing keys keep their names
  and meanings; nothing downstream that reads `entries_failed`, `rows_failed`, or
  `loaded_or_updated_rows` changes.
- `scripts/dev/rehearse_player_page_rebuild.py` drops `_is_out_of_scope_only()`
  and the continue-on-nonzero branch it feeds. After this card the driver aborts
  on **any** nonzero producer exit, as it should.
- `validate official-stats` still consumes both reports without change, and
  `docs/validation/OFFLINE_DATABASE_PREPARATION.md`'s "Producer exit codes on a
  complete rebuild" section is rewritten to say both exit 0.

# Scope

`src/nba_data/scraping/offline_player_stats_backfill.py`,
`src/nba_data/scraping/offline_player_postseason_stats_backfill.py`, their report
dataclasses, the `failure_fields` tuples in `src/nba_data/cli/main.py:460,536`,
`scripts/dev/rehearse_player_page_rebuild.py`, and the corresponding tests.

# Out of scope

The team-season producer (`offline_stats_backfill.py`), which loads from a
manifest already bounded to 2000–2025 and does not have this problem. The
coverage oracle's expectations: `F4E-029` owns those, and the two cards must not
both try to define what "in scope" means — this one reads `core.seasons`, the
same source. Any change to selection, normalization, loading, or parser-version
lineage. Widening or narrowing the archive's season range.

# Impact

`nba-data backfill player-stats` and `backfill player-postseason-stats` exit
codes and report shapes. `scripts/dev/rehearse_player_page_rebuild.py`. Their
unit tests and any CLI test asserting exit codes. No schema change, no migration,
no parser version, no write-path behavior — the same rows load either way; only
the classification and the exit code change.

# Implementation notes

Coordinate with `F4E-029` on ordering. Both cards read the same
`core.seasons` range; whichever lands first should put that lookup somewhere the
second can reuse rather than duplicating the query. Neither may hard-code 2000 or
2025 — the range already exists in
`src/nba_data/scraping/nba_team_season_manifest.py:10-12` and is asserted by
`validate offline-database`.

`F4E-027` also edits both backfill modules. If it is still open, read it before
starting so the two do not conflict line for line.

Verification does not need a full rebuild: unit tests with a seeded scratch
session cover both classifications. Run
`scripts/dev/rehearse_player_page_rebuild.py` once on a scratch database to
confirm the exit-0 criterion end to end and to prove the removed workaround was
not load-bearing.

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — replace the "Producer exit
  codes on a complete rebuild" section with the post-fix behavior, and drop the
  note explaining why the rehearsal driver continues past a nonzero exit.

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
