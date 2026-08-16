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

## What changed

- `src/nba_data/scraping/normalizers/player_page.py` — `_season_end_year` now
  rolls the century forward when the two-digit suffix is numerically below the
  start year's last two digits. `_SEASON_RANGE_RE` was also tightened from
  `\d{2,4}` to `\d{2}|\d{4}`, because a three-digit suffix was previously
  accepted and silently *guessed* at (`2020-021` returned `2021`), which the
  "malformed labels still return `None`" criterion forbids. This is one line
  outside the stated `_season_end_year`-only scope; it is the regex that
  function owns, and no cached page contains a three-digit suffix, so it
  changes nothing on real data.
- Both parser-version constants bumped to `-v2`, with the reason recorded at
  the constant.
- `scripts/recount_player_page_candidates.py` — new cache-only recount.
- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — new "Season Labels And The
  Century Rollover" section.
- `tests/unit/test_player_page_normalizer.py` — parametrized label tests.
- The two CLI-default `-v1` assertions updated to `-v2`.

## Automated validation

- Command: `uv run pytest tests/unit/test_player_page_normalizer.py`
- Result: **82 passed**.

- Command: `uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py`
- Result: **119 passed** (run together with the normalizer tests).

- Command: `uv run ruff check .`
- Result: **All checks passed.**

- Command: `uv run pytest`
- Result: **517 passed, 1 error.** The error is `tests/integration/test_api_postgres.py`
  refusing to run against the developer's populated local `nba` database
  ("found 37 team row(s) and 26 season row(s)"). It is an environment guard,
  not a code failure, it is unrelated to this card, and it reproduces on `main`.
  `uv run python scripts/validate_postgres_local.py` is the isolated-database
  path for that test.

- Command: `uv run python scripts/validate_tasks.py`
- Result: **Task validation passed.**

## Recount evidence

- Command: `uv run python scripts/recount_player_page_candidates.py --progress`
- Output: `reports/player_page_candidate_recount.json` (`reports/` is
  gitignored and `AGENTS.md` forbids committing it — see Known limitations).
- Result: **2,551 pages enumerated, 2,551 processed, 0 unreadable, 0 unparseable
  filenames**, 1,336 s. `player_pages_match_expected: true`.

Season 2000 — the `1999-00` label this card fixes:

| Scope | `stat_scope` | Candidates |
|---|---|---|
| regular season | `player_season_aggregate` | 3,872 |
| postseason | `player_postseason_aggregate` | 1,448 |
| postseason | `player_team_postseason` | 1,448 |
| | **total** | **6,768** |

This independently reproduces the card's prior 6,768 measurement exactly, from a
glob-driven enumeration rather than the discovery helper. It is evidence, not an
acceptance threshold, and it counts candidates — not persisted rows.

Whole-archive totals, with every non-emitted input row carrying a reason:

| Scope | Input rows | Candidates | Not emitted | Unattributed |
|---|---|---|---|---|
| regular season | 161,586 | 131,900 | 29,686 | **0** |
| postseason | 63,250 | 105,096 (52,548 aggregate + 52,548 stint) | 10,702 | **0** |

Reasons for rows that produce no candidate:

- regular season — `superseded_by_full_season_selection` 29,534,
  `ignored_invalid_or_unsupported_rows` 88,
  `ambiguous_multiple_real_team_rows` 64.
- postseason — `invalid_season_row` 10,702 (career/summary rows, whose season
  cell Basketball Reference leaves blank).

The 64 `ambiguous_multiple_real_team_rows` are **fully owned by existing cards**,
not an unattributed category and not a general "traded player with no multi-team
marker" class:

| Cause | Rows | Owner |
|---|---|---|
| Oliver Miller (`milleol01`) 2003-04 DNP-placeholder collision — 2 rows × 8 tables | 16 | F4E-022 |
| Bobby Jones (`jonesbo02`) 2007-08 `5TM` season — 6 rows × 8 tables | 48 | F4E-014 |
| | **64** | |

This matches F4E-022's own census, which records `jonesbo02` 2008 as the only
ambiguous entry that is not the placeholder collision.

`invalid_season_row` is the correct outcome for a blank-season career/summary
row, but the name reads like a parse failure rather than a deliberate skip. A
clearer name (`non_season_summary_row`) belongs with whatever card formalizes
the selection-reason vocabulary, not here — renaming it in this card would
change reason strings that are out of scope.

`balanced: true` and `anomalies: []` for both scopes: every parsed input row is
either attributed to at least one emitted candidate or to a named reason.
Postseason candidates exceed input rows by design — a single real-team row is
emitted both as the season aggregate and as its own team stint.

Resolved season years span **1983–2026** with no pre-1950 value, which is the
signature the century bug would have left.

## Manual happy path

1. `uv run python -c "from nba_data.scraping.normalizers.player_page import _season_end_year; print(_season_end_year({'season': '1999-00'}))"`
2. `uv run python -c "from nba_data.scraping.normalizers.player_page import _season_end_year; print(_season_end_year({'season': '2024-25'}))"`
3. `uv run python scripts/recount_player_page_candidates.py --limit 25 --output /tmp/recount.json`

Expected result: step 1 prints `2000` (not `1900`); step 2 prints `2025`;
step 3 reports `player_pages_enumerated: 2551`, `match=True`, and
`input_rows_unattributed: 0` for both scopes.

## Manual sad path

1. `uv run python -c "from nba_data.scraping.normalizers.player_page import _season_end_year; print(_season_end_year({'season': '2020-021'}))"`
2. `uv run python -c "from nba_data.scraping.normalizers.player_page import _season_end_year; print(_season_end_year({'season': 'Career'}))"`
3. `uv run python scripts/recount_player_page_candidates.py --cache-root /does/not/exist`

Expected result: steps 1 and 2 print `None` — a malformed label is never
guessed at; step 3 exits `1` with
`Player-page cache root does not exist: ...` rather than silently reporting a
zero-page run.

## Known limitations

- **The recount JSON is not committed.** The card scopes "the JSON breakdown it
  writes" under `scripts/`, but `AGENTS.md` lists `reports/` and `data/` as
  never-commit and takes precedence. The script therefore writes to
  `reports/player_page_candidate_recount.json`, which is gitignored. The
  committed deliverable is the script; the JSON is reproducible by running it.
  Flagging the conflict rather than resolving it silently.
- The recount measures **normalized candidates**, not persisted rows, and makes
  no claim about grain resolution. The JSON says so in three explicit fields
  (`measures`, `measures_persisted_rows`, `claims_grain_resolution`).
- The archive's player pages cover full careers, so the recount reports
  candidates for seasons well before 1999 that `core.seasons` (2000–2025) will
  never resolve. That is expected and is not a defect this card introduces.
- `-v1` string literals remain in `tests/unit/test_official_stats_validation.py`
  and `tests/unit/test_player_page_stats_loader.py`. Those supply an arbitrary
  lineage string as test *input*; they do not assert the parser-version
  contract, so they were left alone. The regular/postseason separation
  validator keys on the substring `postseason`, not on the version number, so
  `-v2` needs no validator change.
- **The postseason multi-team bookkeeping is proven by inspection, not by cache
  coverage.** The script reconciles *input rows*, not emitted candidates, since
  a real-team postseason row is emitted twice (aggregate and stint), and it
  attributes a per-group residual to `superseded_multi_team_marker_row`.
  Residuals are computed per player/table/season group, so a positive and a
  negative residual in different groups cannot cancel, and a negative residual
  is recorded as an anomaly. But the archive never exercises that path: the
  postseason outcomes are exactly 52,548 `selected_single_team_row` groups and
  10,702 blank-season rows, with no synthetic-marker and no ambiguous groups, so
  the observed balance is simply 63,250 = 52,548 + 10,702. If this script is
  ever promoted to a reusable validation tool — F4E-017 or F4E-018 are the
  plausible consumers — it needs synthetic unit fixtures for the marker path
  first, plus a schema and a cache digest if its JSON becomes a versioned input.
- The **rebuild-and-diff** and **in-place remediation** cards this card's Out of
  scope defers to do not exist yet under `planning/`, `backlog/`, or `review/`.
  That does not block this card, but the deferral currently points at nothing.
- Nothing was loaded, backfilled, or migrated. No database was read or written.
