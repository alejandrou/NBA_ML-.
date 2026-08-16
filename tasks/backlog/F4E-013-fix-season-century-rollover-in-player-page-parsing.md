---
id: F4E-013
title: Fix the season century rollover in player-page normalization
areas:
  - scraping
  - data-quality
  - testing
priority: 95
depends_on: []
read:
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/scraping/normalizers/player_page.py
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/offline_player_postseason_stats_backfill.py
validation:
  - uv run pytest tests/unit/test_player_page_normalizer.py
  - uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make `_season_end_year` compute the correct end year for a `YYYY-YY` season label
that crosses a century boundary, so `1999-00` resolves to `2000` instead of
`1900`. Parsing only: this card writes nothing to the database.

# Evidence and current state

`_season_end_year` in
[player_page.py:414-435](../../src/nba_data/scraping/normalizers/player_page.py#L414-L435)
ends with:

```python
century = (start_year // 100) * 100
return century + int(end_suffix)
```

For `1999-00` that is `1900 + 0 = 1900`. The century is taken from the *start*
year and never advanced, so any two-digit suffix numerically below the start's
last two digits lands one century early. The archive's first season is `1999-00`,
so this is not a hypothetical: it is the boundary the archive opens on.

A season year of `1900` has no `core.seasons` row, so `_resolve_player_season_id`
cannot resolve a grain id and the row is never persisted. The failure is silent
at query time because nothing asserts that `core.player_seasons` and `stats.*`
agree — see F4E-018.

## Confirmed against the live database

Queried directly against the `nba` database in the running `nba_postgres`
container:

- `core.seasons` contains exactly **2000–2025** and **no row with
  `season_year < 1999`**. Nothing was ever written under a 1900 key.
- **634** `core.player_seasons` rows have no row in
  `stats.player_season_totals`. Of those, **439 are in season 2000** — the
  `1999-00` label, which is exactly the one label in the archive that crosses a
  century. Every other season contributes a tail of roughly 9–13.
- None of the 439 has postseason rows either, consistent with the whole season
  having been dropped rather than partially loaded.

So this bug accounts for **439 of the 634 missing player-seasons**. The other
195 are four separate problems, all now owned: **184** are the short-id discovery
omission (the F4E-012 card), **9** are valid postseason-only seasons and are
correct as loaded, **1** is the `5TM` marker (F4E-014), and **1** is a
"Did not play" placeholder counted as a team row (F4E-022). None of them is this
card's, and none is unexplained.

Two consequences worth stating plainly. The failure is **omission, not
corruption**: no stale or wrongly-keyed row exists to clean up, because
resolution failed before any write. And 439 is the count of *missing
`core.player_seasons` coverage*, which is not the same as the count of
normalized candidates below.

## The 6,768 candidate figure

Measured from the cache in a prior analysis: **6,768 affected normalized
candidates** — 3,872 regular-season aggregates, 1,448 postseason aggregates,
1,448 postseason stints. That figure counts *normalized candidate rows*, not
guaranteed recoverable persisted rows: whether a candidate becomes a row also
depends on the grain resolving and on the loader accepting it. Recount before
starting (see Implementation notes); do not treat 6,768 as an acceptance target.

**The recount must enumerate all 2,551 cached player pages, not 2,515.** The
discovery pattern at
[offline_player_stats_backfill.py:21](../../src/nba_data/scraping/offline_player_stats_backfill.py#L21)
requires `[a-z0-9]{8,10}`, which excludes 36 players whose Basketball Reference
ids are six or seven characters — short surnames such as `foxde01`, `gayru01`,
`linje01`, `qizh01`. A recount driven by current discovery would silently omit
them and understate the figure. Enumerate the cache directly (glob
`players-*.html.gz`) rather than reusing the discovery helper; the discovery
defect itself is owned by the card on the unmerged
`feature/f4e-012-fix-player-page-cache-discovery-contract` branch and is **not**
fixed here.

The two player-page parser-version constants that label this contract in stats
lineage are
[`DEFAULT_PLAYER_STATS_PARSER_VERSION`](../../src/nba_data/scraping/offline_player_stats_backfill.py#L19)
(`player-page-parser-v1`) and
[`DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION`](../../src/nba_data/scraping/offline_player_postseason_stats_backfill.py#L19)
(`player-page-postseason-parser-v1`). Rows written under the buggy contract must
be distinguishable from rows written after it.

# Human decisions or resources

- None.

# Acceptance criteria

- `_season_end_year` rolls the century forward when the two-digit suffix is
  numerically below the start year's last two digits, and leaves every other
  case unchanged.
- Parametrized unit tests cover the archive's full `1999-00` … `2024-25` label
  range, plus the four-digit form `1999-2000`, the plain four-digit form `2000`,
  the non-crossing `2000-01`, and the current-final `2024-25`.
- Malformed labels still return `None` rather than a guessed year.
- Both parser-version constants are bumped to `-v2`
  (`player-page-parser-v2`, `player-page-postseason-parser-v2`), and any test or
  fixture asserting the `-v1` strings is updated.
- A cache-only recount script records **exact per-table counts of normalized
  candidate rows** after the fix, broken down by season year and source table,
  and **enumerates a reason for every candidate that the normalizer does not
  emit**. A bare "≤ N will resolve" statement does not satisfy this — including
  "≤ 439", which is the measured *current* gap, not a target.
- The recount covers all **2,551** cached player pages and states that count
  explicitly, so a regression to 2,515 is visible rather than silent.
- The script states plainly that it measures **candidates, not persisted rows**,
  and does not claim grain resolution. See the note below on why.
- No database reads, no database writes, no migration, no backfill run as part of
  this card.

# Scope

- `src/nba_data/scraping/normalizers/player_page.py` — `_season_end_year` only.
- `src/nba_data/scraping/offline_player_stats_backfill.py` and
  `offline_player_postseason_stats_backfill.py` — the parser-version constants.
- `scripts/` — the cache-only recount script and the JSON breakdown it writes.
  An earlier revision required this recount in the acceptance criteria but never
  named it in scope, leaving the deliverable homeless.
- `tests/unit/` — the parametrized season-label tests and any `-v1` assertions.

# Out of scope

Loading, backfilling, or repairing persisted rows — the future
**rebuild-and-diff** and **in-place remediation** cards own that.
The multi-team marker predicate, which is F4E-014 and carries its own version
label. Team-season parsing, which does not use this function.

# Impact

Every player-page stats row's `season_year`, and therefore grain resolution in
both player-page loaders. The stored `parser_version` string changes, so lineage
queries that filter on `player-page-parser-v1` must be updated. The team-season
parser version is untouched.

# Implementation notes

Fix by comparison, not by a hard-coded pivot: if `int(end_suffix)` is less than
`start_year % 100`, add 100 to the century. A fixed "years below 50 mean 2000s"
rule would be wrong for this archive and wrong again for the next one.

Re-run the 6,768 recount from cache before starting (~10 minutes, cache-only, no
database). The figure in this card is the prior measurement and is evidence, not
an acceptance threshold.

**The recount cannot measure "resolution", and an earlier revision of this card
asked it to.** Whether a normalized candidate becomes a persisted row depends on
`core.seasons`, `core.players`, and `core.player_seasons` — all database state.
A cache-only script has no access to any of it, so "enumerate every natural key
that still does not resolve" was unsatisfiable as written. The criterion is now
scoped to what the cache can answer: how many candidates the normalizer emits,
and why it drops the ones it drops. Proving that those candidates *land* is the
future rebuild-and-diff card's job, which is exactly why that card exists.

Emit `-v2` here. F4E-014 emits `-v3` so each card's contract stays attributable
in stats lineage. **This card must merge first** — F4E-014 declares
`depends_on: F4E-013`, and merging it first would let this card's `-v2` overwrite
its `-v3`.

# Durable knowledge updates

- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — record that a `YYYY-YY`
  label may cross a century and how the end year is derived, so the next parser
  does not reintroduce this.

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
