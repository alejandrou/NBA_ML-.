---
id: F4E-012
title: Reconcile the player-id contract between acquisition and cache discovery
areas:
  - scraping
  - data-quality
priority: 55
depends_on: []
read:
  - docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md
  - docs/architecture/IMPACT_MAP.md
validation:
  - uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make cache discovery accept every player id that acquisition is allowed to write,
and make an empty or missing cache root fail loudly instead of reporting a
successful run that processed nothing.

This is follow-up step 2 from `F4E-011`, minted because the defect is now
measured rather than suspected. It does not depend on `F4E-011` resolving the
separate "why did that particular run report zero" question.

# Evidence and current state

Two ends of the same pipeline disagree about how long a Basketball Reference
player id may be.

- Acquisition validates ids as `^[a-z][a-z0-9]{5,9}$` — 6 to 10 characters —
  at `src/nba_data/scraping/player_page_acquisition.py:22`.
- Discovery requires 8 to 10 characters, via `_PLAYER_ID` in the filename regex
  at `src/nba_data/scraping/offline_player_stats_backfill.py:20-23`:
  `^players-(?P<initial>[a-z])-(?P<player_id>[a-z0-9]{8,10})\.html-[0-9a-f]{16}\.html\.gz$`

Pages for 6-7 character ids can therefore be acquired and then never processed.

Measured against `data/raw/html/basketball-reference/` on 2026-08-13, id length
by cached player page:

| id length | files | discovered |
|---|---|---|
| 6 | 2 | no |
| 7 | 34 | no |
| 8 | 213 | yes |
| 9 | 2302 | yes |

**36 acquired player pages are silently unreachable** — 2 six-character and 34
seven-character ids, including `acyqu01`, `beysa01`, `beyty01`, `bolbo01`. They
are skipped with no warning, no counter, and no entry in the report.

The blast radius is both player backfills:
`offline_player_postseason_stats_backfill.py:13` imports
`_discover_player_cache_entries` directly, so one regex governs regular-season
and postseason processing alike.

Separately, `_discover_player_cache_entries` returns `[]` when the cache root does
not exist (`offline_player_stats_backfill.py:156-158`). Because
`run_offline_player_stats_backfill` sets `player_pages_processed` to exactly
`len(cache_entries)` (line 118), a wrong working directory or a stale
`SCRAPER_CACHE_DIR` yields a clean report of zero rather than an error.
`Settings.scraper_cache_dir` defaults to the relative `Path("data/raw/html")`
(`src/nba_data/config/settings.py:22`), so it resolves against the process
working directory, and `get_settings()` is `@lru_cache`d.

# Human decisions or resources

- None.

# Acceptance criteria

- The discovery filename regex accepts the same player-id range acquisition
  accepts. The two bounds are expressed once and shared, so they cannot drift
  apart again — a test asserts the discovery pattern and
  `player_page_acquisition._PLAYER_ID_RE` agree on the accepted length range.
- A unit test fixture containing 6-, 7-, 8-, 9-, and 10-character player-id
  filenames is discovered in full; before the fix the 6- and 7-character cases
  are the ones that fail.
- The postseason backfill inherits the fix through the shared function, proven by
  an equivalent test in
  `tests/unit/test_offline_player_postseason_stats_backfill.py`.
- A filename that is genuinely malformed — wrong prefix, missing digest, non-gzip
  suffix — is still rejected. The fix widens the id range only; it does not
  loosen the rest of the pattern.
- A missing cache root raises rather than returning an empty list, and the error
  message names the resolved absolute path that was checked.
- An existing cache root that contains no matching player page is distinguishable
  from a missing root: it still returns zero entries, but the run reports that
  zero-match condition explicitly rather than silently.
- Both conditions are covered by tests using `tmp_path`, with no dependency on
  the real `data/` directory.

# Scope

`src/nba_data/scraping/offline_player_stats_backfill.py`,
`src/nba_data/scraping/offline_player_postseason_stats_backfill.py`,
`src/nba_data/scraping/player_page_acquisition.py` (to export the shared bound
only — its validation behaviour does not change), and their unit tests.

# Out of scope

Acquiring any new cache, or any network request. Running a backfill against a
real or shared database. Changing `Settings.scraper_cache_dir` resolution or the
`get_settings()` cache — if a wrong working directory turns out to be the actual
cause of a specific failed run, that is `F4E-011`'s question, and an absolute-path
default is its own card. Parser or loader behaviour. Any schema or migration
change.

# Impact

Player-page acquisition, regular-season player stats, and postseason player stats
flows in `docs/architecture/IMPACT_MAP.md`; cross-cutting couplings 1 through 4
apply. Both `backfill player-stats` and the postseason equivalent in
`src/nba_data/cli/main.py` change behaviour: 36 more pages become processable
from the existing cache, and a misconfigured cache root now errors where it
previously reported success.

Callers that relied on an empty list for a missing root will now see an
exception — check `src/nba_data/cli/main.py` and both backfill entry points
before changing the return contract.

# Implementation notes

Prefer deriving the discovery pattern from one shared constant over editing
`{8,10}` to `{5,9}` in place; the point of the card is that two hardcoded ranges
drifted. Keep `re.IGNORECASE` on both patterns.

`_discover_player_cache_entries` decompresses every candidate to check it is
non-empty, so a full scan is I/O-heavy. Keep tests on `tmp_path` fixtures.

The 36 currently-unreachable pages are the natural manual verification, but
processing them writes to a database — treat that as the user's review step, not
part of this card's automated validation.

# Durable knowledge updates

- `docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md` — update the "Known contract
  mismatch" section with the reconciled range, or remove it if the fix closes it.
- `docs/architecture/IMPACT_MAP.md` — update coupling 2 with the resolved range.

# What changed

- `player_page_acquisition.py` now exposes `PLAYER_ID_MIN_LENGTH`,
  `PLAYER_ID_MAX_LENGTH`, and `PLAYER_ID_PATTERN`. `_PLAYER_ID_RE` is built from
  that fragment; its accepted range is unchanged (6-10 characters).
- `offline_player_stats_backfill._PLAYER_CACHE_FILE_RE` interpolates
  `PLAYER_ID_PATTERN` instead of restating `{8,10}`. The rest of the filename
  pattern — prefix, single-letter initial, 16-hex digest, `.html.gz` suffix — is
  untouched.
- New `PlayerCacheRootNotFoundError(ValueError)` and `resolve_player_cache_root`:
  a missing or non-directory cache root raises, naming the resolved absolute path
  and pointing at `SCRAPER_CACHE_DIR` and the working directory. `ValueError` is
  the deliberate base class so the existing CLI `except ValueError` turns it into
  a `typer.BadParameter` rather than a traceback.
- New `discovery_status_for`. Both reports gained `cache_root` and
  `discovery_status` (`ok` / `no_matching_pages`), serialized in `to_dict`, so an
  existing-but-unmatched root is visible in the JSON report. The status is
  computed before `--limit` truncation.
- The postseason backfill imports the two new helpers alongside the three private
  ones it already shared, so both commands move together.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py`
- Result: 37 passed.
- Command: `uv run ruff check .`
- Result: All checks passed.
- Command: `uv run pytest`
- Result: 443 passed, 1 error — `tests/integration/test_api_postgres.py::test_postgres_api_reads_teams_and_filtered_seasons`
  errors at setup with "PostgreSQL database is not isolated (before seeding):
  found 37 team row(s) and 26 season row(s)". That is `_fail_unless_empty`, the
  test's own fixture-level guard, counting rows already in the local PostgreSQL
  database before the test seeds anything. It depends only on database state; this
  card writes no rows and touches no API, database, or settings code.

New tests, all offline on `tmp_path`:

- `test_offline_player_stats_backfill_discovers_every_accepted_player_id_length`
  and its postseason twin — one cached page per accepted length (6, 7, 8, 9, 10),
  all five discovered and processed. Against the old `{8,10}` regex the 6- and 7-
  character cases are the ones that fail.
- `test_cache_discovery_and_acquisition_agree_on_player_id_length_range` —
  parametrized over lengths 1-13, asserts the discovery pattern and
  `player_page_acquisition._PLAYER_ID_RE` accept exactly the same lengths.
- `test_offline_player_stats_backfill_still_rejects_malformed_cache_filenames` —
  wrong prefix, missing digest, non-hex digest, non-gzip suffix, and a two-letter
  initial are all still rejected next to one valid control file.
- `test_cache_discovery_rejects_player_ids_acquisition_cannot_write` — sharing the
  pattern also narrows discovery's first character from `[a-z0-9]` to `[a-z]`. That
  narrowing is deliberate and pinned here: acquisition cannot write a digit-leading
  id, and the real cache contains none (checked read-only across 2551 pages).
- `..._raises_when_cache_root_is_missing` and
  `..._reports_an_existing_but_unmatched_cache_root`, in both test modules.
- `test_cli_player_stats_reports_a_missing_cache_root_without_a_traceback` and its
  postseason twin — invoke the real backfill through the CLI against a missing
  `SCRAPER_CACHE_DIR` with a faked engine and session, and assert a clean
  `SystemExit` carrying the resolved path, with no report file written. Each
  command has its own copy of `except ValueError`, so each needs its own guard;
  verified to fail if `PlayerCacheRootNotFoundError` stops subclassing `ValueError`.

## Manual happy path

1. `uv run nba-data backfill player-stats --execute-approved-player-stats-backfill --player acyqu01 --output reports/f4e-012-acyqu01.json`
   (`acyqu01` is 7 characters — unreachable before this card).
2. Read the report: `player_pages_processed` is 1, `discovery_status` is `ok`,
   and `cache_root` is the absolute path you expected.
3. Repeat without `--player` to process the remaining 35 short-id pages.

Expected result: the page is found, parsed, and loaded; rerunning is idempotent.

**This writes rows to a real database — it is your call, not the card's.** The
card's automated validation does not touch `data/` or any database.

## Manual sad path

1. `SCRAPER_CACHE_DIR=/tmp/definitely-not-a-cache uv run nba-data backfill player-stats --execute-approved-player-stats-backfill`
2. Read the error.
3. Point `SCRAPER_CACHE_DIR` at an existing but empty directory and rerun.

Expected result: step 2 exits 2 with Typer's `Invalid value:` error panel naming
the resolved absolute path that was checked, instead of reporting a successful run
over zero pages. On a narrow terminal Rich wraps that path across panel lines —
cosmetic, but widen the window if you want to copy it. Step 3 succeeds with
`player_pages_processed: 0` and `discovery_status: "no_matching_pages"` — the two
conditions are now distinguishable.

## Known limitations

- Both new report fields are additive; anything parsing an older report JSON will
  simply not see them.
- An existing-but-unmatched cache root still exits 0. Only `discovery_status`
  distinguishes it, which is what the card asked for, but a caller that reads just
  the exit code still cannot tell a real empty run from a misconfigured root.
- Discovery gunzips every candidate file to check readability, then processing
  gunzips it again. Pre-existing, untouched here, and it doubles the decompression
  work over the ~2551 cached pages.
- A corrupt or empty cache file is skipped silently by discovery rather than
  reported. A root full of unreadable pages would therefore report
  `no_matching_pages` instead of naming them. Pre-existing behaviour that the new
  status label inherits.
- Coupling 1 in `IMPACT_MAP.md` still stands: the rest of the cache filename shape
  is re-derived in `cache_inventory.py` rather than imported. Only the player-id
  range was unified here.
- `Settings.scraper_cache_dir` still defaults to a relative path resolved against
  the working directory, and `get_settings()` is still `@lru_cache`d — out of
  scope by the card, and now loud rather than silent for these two commands only.
