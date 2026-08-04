---
id: F4E-011
title: Diagnose empty player-page stats backfill discovery
areas:
  - planning
  - scraping
  - data-quality
priority: 60
depends_on: []
read:
  - docs/architecture/IMPACT_MAP.md
  - docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md
validation: []
critical_actions: []
---

# Goal

Establish why `backfill player-stats` reported zero processed player pages, using
only offline inspection. This card diagnoses; it does not fix, acquire, or load
anything.

# Evidence and current state

Discovery is a single function shared by both player backfills:
`_discover_player_cache_entries` in
`src/nba_data/scraping/offline_player_stats_backfill.py`. It accepts a cached
file only when all three of these hold:

1. the resolved path contains a literal `basketball-reference` path segment;
2. the filename fullmatches
   `^players-(?P<initial>[a-z])-(?P<player_id>[a-z0-9]{8,10})\.html-[0-9a-f]{16}\.html\.gz$`;
3. the gzip opens and is non-empty.

`run_offline_player_stats_backfill` sets `player_pages_processed` to exactly
`len(cache_entries)`, so a report of `0` means discovery itself returned nothing —
not that parsing or loading failed.

Measured against the working tree on 2026-08-03, from the repository root:

- `data/raw/html/basketball-reference/` exists and holds 3326 `.html.gz` files;
- 2551 are `players-*`, of which **2515 match the discovery regex**;
- 775 are `teams-*`;
- **36 player pages do not match**, all because their player id is 7 characters:
  `players-a-acyqu01...`, `players-b-beysa01...`, `players-b-beyty01...`,
  `players-b-bolbo01...`, and 32 more.

Two conclusions follow, and they point in different directions:

- **The 36 unmatched files are a real, confirmed defect.** Acquisition validates
  player ids as `^[a-z][a-z0-9]{5,9}$` (6-10 characters,
  `src/nba_data/scraping/player_page_acquisition.py`) while discovery demands
  8-10. Pages for 6-7 character ids can be acquired and then never processed.
  This is a contract mismatch between the two ends of the same pipeline.
- **The 36 files do not explain a count of zero.** From the repository root
  discovery finds 2515 entries. Zero requires something upstream of the regex:
  `cache.root_dir` not existing (the function returns `[]` immediately),
  a `--player` filter matching nothing, or a `--limit` of zero.

The most likely upstream cause is the cache root. `Settings.scraper_cache_dir`
defaults to the **relative** `Path("data/raw/html")`
(`src/nba_data/config/settings.py`), so it resolves against the process working
directory; `get_settings()` is `@lru_cache`d, so an environment change after the
first call is ignored. Running the command from anywhere but the repository root,
or with a stale `SCRAPER_CACHE_DIR`, yields silent zero rather than an error.

One ambiguity remains in the original report: "discovers zero pages" could mean
`player_pages_processed: 0` (discovery) or `rows_loaded_or_updated: 0` with pages
processed (unresolved players or seasons, i.e. an unpopulated `core`). These have
different causes and different fixes.

# Human decisions or resources

- [ ] Which working directory and `SCRAPER_CACHE_DIR` value did the failing run
      actually use, and can you paste the JSON report it produced? The report
      distinguishes `player_pages_processed: 0` from
      `rows_loaded_or_updated: 0`, which decides whether this is a discovery
      problem or a `core` population problem.

# Acceptance criteria

Not final — this card is not ready to start. Draft direction:

- The failing run's report is classified as either a discovery failure or a
  load-resolution failure, with evidence.
- If discovery: the exact gate that rejected the files is named.
- The 6-7 character player-id mismatch is quantified against the current cache
  and confirmed or ruled out as a contributor.
- Findings are written up; no production code is changed by this card.

# Scope

Read-only inspection of `src/nba_data/scraping/offline_player_stats_backfill.py`,
`player_page_acquisition.py`, `cache.py`, `config/settings.py`, their tests, and
the local cache directory listing.

# Out of scope

Changing discovery, the regexes, or settings resolution. Acquiring any cache.
Running a backfill against a real database. Any network request. Any schema or
migration change.

# Impact

Touches the player-page acquisition, regular-season player stats, and postseason
player stats flows in `docs/architecture/IMPACT_MAP.md`. Because
`offline_player_postseason_stats_backfill.py` imports
`_discover_player_cache_entries` directly, any eventual fix changes both backfill
commands. Cross-cutting couplings 1 through 4 in the impact map all apply.

# Implementation notes

Diagnose offline only. `_discover_player_cache_entries` decompresses every
candidate file, so a full scan is I/O-heavy but harmless; scope it with a prefix
when iterating.

Proposed follow-up split, **named by boundary, ids deliberately not minted** —
`prepare-task` mints them once this diagnosis confirms which pieces are real:

1. *Diagnose* — this card.
2. *Fix player-page cache discovery and diagnostics* — reconcile the player-id
   contract between acquisition and discovery, and make an empty or missing cache
   root report loudly instead of returning zero.
3. *Acquire missing player-page cache* — the **only** step that would be a
   critical action; it contacts Basketball Reference and needs the user's direct
   instruction at the time it runs.
4. *Validate a player stats smoke backfill* — a small bounded run proving the
   pipeline end to end.

Minting ids 2-4 now would create cards for an unconfirmed hypothesis. If the root
cause turns out to be only the working directory, steps 2 and 3 shrink or vanish.

# Durable knowledge updates

If the player-id contract is confirmed broken, update the "Known contract
mismatch" section of `docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md` and
coupling 2 in `docs/architecture/IMPACT_MAP.md` with the resolved range.

# Review evidence

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
