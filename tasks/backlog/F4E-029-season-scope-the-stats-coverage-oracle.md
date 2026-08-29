---
id: F4E-029
title: Season-scope the stats-coverage oracle to the seasons the archive loads
areas:
  - data-quality
  - testing
priority: 58
depends_on:
  - F4E-018
read:
  - src/nba_data/validation/official_stats.py
  - src/nba_data/validation/stats_coverage.py
  - src/nba_data/validation/offline_database.py
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
validation:
  - uv run pytest tests/unit/test_official_stats_validation.py tests/unit/test_stats_coverage_artifact.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make `validate official-stats` compare the coverage artifact against the seasons
the archive actually loads, so a complete, correct rebuild exits 0 instead of
reporting 39,972 rows the archive was never meant to hold.

# Evidence and current state

`F4E-024` rebuilt the entire player-page archive at `-v4` on a scratch database
and measured the result. Every grain came out exactly as predicted — 12,667
distinct regular-season player-seasons (+625), 5,301 postseason player-seasons
(+235), `coverage_unexpected_<dimension>_row` **zero in all four dimensions** —
and `validate official-stats` still exited 1, with three findings:

| Finding | Count |
|---|---|
| `coverage_missing_regular_aggregate_row` | 19,692 |
| `coverage_missing_postseason_aggregate_row` | 10,140 |
| `coverage_missing_postseason_team_stint_row` | 10,140 |

Every sampled example is a **pre-2000 season**. The cause is a scope mismatch
between the oracle and the archive, not a defect in the rebuild:

- `build_stats_coverage_artifact` traverses cached player pages and emits an
  entry for every season those pages carry — Basketball Reference player pages
  cover **1983–2026**. `src/nba_data/validation/stats_coverage.py:397-408` unions
  every season found in the parsed tables into `seasons` with no range filter.
- The archive deliberately loads **2000–2025** only. That range is a stated
  constant in two places:
  `src/nba_data/scraping/nba_team_season_manifest.py:10-12`
  (`MANIFEST_ID = "nba-team-season-2000-2025"`, `SEASON_START_YEAR = 2000`,
  `SEASON_END_YEAR = 2025`) and
  `src/nba_data/validation/offline_database.py:38-39`
  (`expected_start_year = 2000`, `expected_end_year = 2025`).
- `_expected_aggregate_keys` (`official_stats.py:1034-1043`) and
  `_expected_team_stint_keys` (`:1045-1060`) build the expected key sets from
  **every** artifact entry, and the dimension loop at `:978-1024` diffs them
  against the persisted keys. Nothing narrows either side to the loaded range.

Restricted to 2000–2025 the artifact expects exactly **101,336** regular
aggregate and **42,408** postseason aggregate rows — precisely what the rebuild
produced. The oracle and the archive agree completely inside the archive's own
scope; they only disagree about seasons the archive does not claim to hold.

This is not cosmetic. `validate official-stats` is the acceptance gate for
applying the `-v4` rebuild to the persistent `nba` database, and it can never
pass while the oracle asks for pre-2000 rows. Two of `F4E-024`'s acceptance
criteria are recorded as unmet for this reason alone.

# Human decisions or resources

- [x] Which season range is authoritative — the archive's 2000–2025, already
  settled in code at `nba_team_season_manifest.py:10-12` and asserted by
  `validate offline-database`. This card scopes the oracle to it rather than
  reopening the range.

# Acceptance criteria

- Expected coverage keys are narrowed to the seasons the archive loads, on both
  sides of every one of the four dimension diffs. The artifact keeps recording
  what the **cache** holds — it stays database-free and its entry count does not
  shrink — while the comparison compares like with like.
- The scoping source is the database, not a hard-coded literal: the comparison
  reads the season years present in `core.seasons` for the league under
  validation. A second copy of `2000`/`2025` is not introduced anywhere.
- On the `F4E-024` rebuild state, `validate official-stats` reports **zero**
  `coverage_missing_<dimension>_row` findings, keeps reporting zero
  `coverage_unexpected_<dimension>_row` findings, and **exits 0**.
- The report still shows the scoping in `coverage_summary.dimensions`, so a
  reader can see how many artifact entries were excluded and why. A silent drop
  is not acceptable — an out-of-scope season must be visible as out-of-scope, not
  invisible.
- A genuinely missing in-range row is still caught. A unit test deletes one
  in-range persisted key and asserts `coverage_missing_regular_aggregate_row`
  fires with that key in `examples`.
- An out-of-scope row that *is* persisted still fails. A unit test persists a key
  for a season outside `core.seasons` and asserts it is reported — scoping
  narrows what is *expected*, never what is *allowed*.
- Tests cover the boundary years explicitly: 1999 (excluded), 2000 (included),
  2025 (included), 2026 (excluded).
- `validate offline-database` still asserts `core.seasons` spans 2000–2025
  exactly, unchanged. That check is what stops season-scoping from becoming a
  blind spot, and this card must not weaken it.

# Scope

`src/nba_data/validation/official_stats.py` — the coverage comparison, its
expected-key helpers, and the dimension summary. Its unit tests. If the artifact
needs to carry the season of each entry more explicitly to make the comparison
readable, `src/nba_data/validation/stats_coverage.py` may gain a read-only
accessor — it already stores `season_year` per entry.

# Out of scope

Changing the archive's season range, `core.seasons` seeding, or the acquisition
manifest. Making the artifact database-aware — it is deliberately DB-free and
must stay so. The producers' exit codes: `F4E-030` owns those. Any change to
loaders, normalizers, parsers, or parser-version lineage. Any write path.

# Impact

`nba-data validate official-stats` exit code and its `coverage_violations`
findings. `coverage_summary.dimensions` gains scoping counts.
`tests/unit/test_official_stats_validation.py`. No schema change, no migration,
no write path, no parser version. Unblocks the acceptance gate that `F4E-031`
depends on.

# Implementation notes

Prefer scoping in the comparison over filtering at build time. The artifact's
value is that it is a faithful, database-free record of what the cache contains;
if a future season range widens, a build-time filter would silently produce a
stale artifact, whereas a comparison-time scope adapts on the next run.

Read `tasks/review/F4E-024-rebuild-the-player-page-stats-archive-at-parser-v4.md`
(or `tasks/done/` once it moves) before starting. Its `# Review evidence` records
the exact counts above and the arithmetic that proves 19,692 / 10,140 / 10,140
are precisely the out-of-scope expectations — reproduce that arithmetic rather
than trusting this card's summary of it.

Verification does not require a 70-minute rebuild. The unit tests carry the
boundary cases. A full re-rehearsal via
`scripts/dev/rehearse_player_page_rebuild.py` confirms the exit-0 criterion end
to end and is worth one run before the card moves to review, on a scratch
database only.

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — the "Known finding: the
  coverage oracle is not season-scoped" subsection becomes a resolved note, and
  the handover procedure's acceptance shape becomes "exits 0".
- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — if it describes the coverage
  comparison, record that expectations are scoped to `core.seasons`.

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
