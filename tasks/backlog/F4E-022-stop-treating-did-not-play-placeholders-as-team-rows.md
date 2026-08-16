---
id: F4E-022
title: Stop treating "Did not play" placeholders as team rows
areas:
  - scraping
  - data-quality
  - testing
priority: 90
depends_on:
  - F4E-014
read:
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/scraping/normalizers/player_page.py
  - src/nba_data/scraping/loaders/player_page_stats.py
  - src/nba_data/scraping/loaders/team_season_stats.py
validation:
  - uv run pytest tests/unit/test_player_page_normalizer.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Teach `_select_full_season_row` that a "Did not play" placeholder is not a team
row. It is currently counted as one, which drops a real season in one case and
emits 577 unloadable rows in the rest. Parsing only: this card writes nothing to
the database.

# Evidence and current state

## What a DNP placeholder actually is

Basketball Reference prints a placeholder row for a season a player missed
entirely. It has **no team cell**, and its `age` cell carries the reason:

```python
{'year_id': '2003-04', 'age': 'Did not play - other pro league'}
```

Measured across all 2,551 cached player pages, **1,380 distinct
`(player, season)` pairs** carry such a row, under **22 distinct reason
strings** — `other pro league` (8,946 cells), `injury` (1,256), `waived` (198),
`unsigned` (144), `retired` (136), `illness` (56), and sixteen more including
`COVID-19`, `military service`, `mental health`, and the bare `Did not play -`.

**This corrects a claim carried by earlier revisions of F4E-017 and the audit
disposition**, both of which said DNP rows normalize to values that are entirely
`None`. They do not. The row normalizes to `{'age': '<the reason string>'}` —
one non-null, non-numeric value — and everything below follows from that.

## Defect 1 — a DNP row plus a real row loses the real season

[`_select_full_season_row`](../../src/nba_data/scraping/normalizers/player_page.py#L373-L385)
partitions a season's rows with:

```python
real_team_rows = [row for row in season_rows if _team_code(row) not in MULTI_TEAM_CODES | IGNORED_TEAM_CODES]
```

`_team_code` returns `None` for a placeholder, and `None` is not in either
frozenset, so **the placeholder is counted as a real team row**. A season
carrying a placeholder *and* a real row therefore has two "real" rows and
returns `ambiguous_multiple_real_team_rows`, selecting nothing.

Reproduced against the cache — **Oliver Miller (`milleol01`), 2003-04**:

| Table | Raw rows | Team codes | Selection | Rows selected |
|---|---|---|---|---|
| all 8 supported | 2 | `None`, `MIN` | `ambiguous_multiple_real_team_rows` | **0** |

His real row is complete and ordinary — 48 games, 506 minutes, 121 points for
MIN — and it normalizes cleanly to 28 values. It is discarded in all eight
tables. Confirmed in the live `nba` database: `milleol01` / 2004 has a
`core.player_seasons` row and **0 rows in `stats.player_season_totals`**.

**An exhaustive scan of all 2,551 cached pages finds exactly one such
collision** — this one. The only other season reaching
`ambiguous_multiple_real_team_rows` is `jonesbo02` 2008, which is the `5TM`
marker owned by F4E-014, not a placeholder collision.

## Defect 2 — a DNP-only season emits eight rows that cannot load

When a placeholder is the season's *only* row it is not ambiguous — it is
`selected_single_team_row`, and the normalizer emits **8 rows** whose entire
payload is the reason string:

```text
-> totals  team None  values {'age': 'Did not play - other pro league'}
```

`age` maps to an `Integer` column, so
[`_stats_values`](../../src/nba_data/scraping/loaders/team_season_stats.py#L930)
raises before any write:

```text
ValueError: Expected integer-compatible value, got 'Did not play - other pro league'.
```

The loader turns that into `status="failed"`, `reason="invalid_values"`, per row.

**This is the mechanism behind every failed entry in the checked-in report.**
`reports/player-stats-backfill-2000-2025.json` holds **577 entries with
`status="failed"`**, all under the single reason
`"Player-page stats loader reported failed rows."` Sampling 60 failed and 60
loaded entries and re-parsing their cached pages: **60/60 failed entries carry a
DNP row; 4/60 loaded entries do.** 572 of the 577 still loaded rows from their
other seasons; the 5 that loaded nothing are players whose every archived season
is a placeholder.

So the archive is not losing data here — the rows were never loadable — but every
run reports 577 failures that are actually one normalizer bug, and no operator
can distinguish them from a real failure.

## Where this sits in the 634

Correcting the audit's decomposition of the 634 `core.player_seasons` rows with
no regular-season aggregate stats:

| Bucket | Count | Owner |
|---|---|---|
| Season 2000, century rollover | 439 | F4E-013 |
| Short-id discovery omission | 184 | the F4E-012 card |
| Valid postseason-only seasons | **9** | none — correct as loaded |
| `jonesbo02` 2008, `5TM` | 1 | F4E-014 |
| `milleol01` 2004, placeholder collision | **1** | **this card** |
| **Total** | **634** | |

Miller was previously counted among ten "valid postseason-only" seasons. He is
not one: he played 48 regular-season games. The other nine — `adamsja01` 2020,
`hollajo02` 2016, `jeffrda01` 2023, `jonesdw02` 2013, `lawsoty01` 2018,
`mcgratr01` 2013, `thomptr01` 2023, `vildolu01` 2022, `wrighdo01` 2016 — carry a
placeholder and no real row, and are correct as loaded.

# Human decisions or resources

- None.

# Acceptance criteria

- A DNP placeholder is recognized explicitly, by a named predicate, and is
  **excluded from the real-team-row candidates** in `_select_full_season_row`.
- The predicate keys on the placeholder's structure — no team code, and an `age`
  cell matching the `Did not play` marker — and must match all 22 reason strings
  found in the cache, including the bare `Did not play -`. It must not match a
  row that merely lacks a team code for some other reason; such a row remains
  unselectable and keeps its current reason.
- **`milleol01` 2003-04 selects 8 rows**, one per supported table, from the real
  `MIN` row — a checked-in fixture asserts this, and asserts the selected values
  include `games=48` and `pts=121` so a placeholder can never satisfy the test.
- A season whose only row is a placeholder selects **0 rows** with a distinct,
  named reason such as `did_not_play_season` — not
  `selected_single_team_row`, and not `no_supported_team_row`, so the two causes
  stay distinguishable in the selection entries.
- The nine valid postseason-only seasons above still yield their postseason rows
  unchanged. A fixture covers at least `mcgratr01` 2013, asserting 16 postseason
  rows and 0 regular-season rows.
- Re-running the player-stats backfill over the cache would report **0 entries
  with `status="failed"`**. Assert this at the normalizer level — no row is
  emitted whose values cannot coerce — rather than by running a backfill.
- The parser-version constants are bumped to **`-v4`**
  (`player-page-parser-v4`, `player-page-postseason-parser-v4`).
- No database writes, no migration, no backfill run as part of this card.

# Scope

- `src/nba_data/scraping/normalizers/player_page.py` — the placeholder predicate
  and `_select_full_season_row`.
- `src/nba_data/scraping/offline_player_stats_backfill.py` and
  `offline_player_postseason_stats_backfill.py` — the parser-version constants.
- `tests/fixtures/` — checked-in cached HTML for `milleol01` and `mcgratr01`.
  Tests must read fixtures, never `data/`, which is untracked.
- `tests/unit/` — the predicate, the two fixtures, and the no-uncoercible-values
  assertion.

# Out of scope

Repairing the persisted archive — the future rebuild-and-diff and in-place
remediation cards own that. The century fix (F4E-013) and the marker predicate
(F4E-014), which this card sequences after. Changing `_stats_values` or the
loader's coercion: the loader is correct to reject a string in an integer column,
and weakening it would hide the next defect of this shape.

# Impact

Player-page normalization for 1,380 player-seasons, and one recovered season.
The 577 failed report entries go to zero, which changes what F4E-016's exit-code
contract observes — see its implementation notes. `parser_version` strings change
again, so lineage filters must expect `-v4`.

# Implementation notes

**Merge order is fixed:** F4E-013 (`-v2`) → F4E-014 (`-v3`) → this card (`-v4`).
All three edit the same two constants, and a card landing out of order downgrades
the label while adding a fix. This card declares `depends_on: F4E-014`, which
declares `depends_on: F4E-013`, so the chain is enforced by the lifecycle.

Prefer excluding the placeholder over special-casing the ambiguity. Treating
"two real rows" as recoverable by picking one would be a guess; recognizing that
one of them was never a team row is a fact about the source.

Note the asymmetry worth preserving: a placeholder means *this season has no
regular-season stats*, which is a real assertion the coverage classifier
(F4E-017) needs. Do not discard it silently — record it as a selection entry so
the classifier can read it.

# Durable knowledge updates

- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — record the placeholder row
  shape, that its `age` cell carries the reason rather than a number, the 22
  observed reason strings, and that a placeholder is never a team row.

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
