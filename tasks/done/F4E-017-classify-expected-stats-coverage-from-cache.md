---
id: F4E-017
title: Build a cache-derived official-stats coverage artifact
areas:
  - scraping
  - data-quality
  - testing
  - documentation
priority: 70
depends_on:
  - F4E-012
  - F4E-013
  - F4E-014
  - F4E-022
  - F4E-025
read:
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - src/nba_data/scraping/cache_inventory.py
  - src/nba_data/scraping/parsers/player_page.py
  - src/nba_data/scraping/parsers/team_season.py
  - src/nba_data/scraping/normalizers/player_page.py
  - src/nba_data/scraping/normalizers/team_season.py
  - src/nba_data/scraping/offline_player_stats_backfill.py
validation:
  - uv run pytest tests/unit
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Build a deterministic, database-free JSON artifact that states the exact
official-stats natural keys implied by the cached team-season and player pages.
F4E-018 will compare this independent expectation set with PostgreSQL.

# Evidence and current state

The current official-stats validator checks schema shape, grains, numeric
ranges, source metadata, and report totals. It cannot answer whether a specific
player-season row that should exist is absent. The archive audit found several
such omissions even though aggregate report totals reconciled.

One cache source is insufficient:

- player pages are authoritative for regular aggregate, postseason aggregate,
  and postseason team-stint rows;
- team-season pages are authoritative for regular roster and team-stint rows.

The artifact therefore traverses both cache families. It derives expectations
from parsed source rows and small source-semantic predicates, not from persisted
rows or from the same normalizer selection result the loaders consume. Reusing
normalizer output as the oracle would make a normalizer defect disappear from
both the database and the expectation set.

The prerequisite fixes are explicit dependencies. F4E-012 supplies complete
player-page discovery, F4E-013 supplies correct season-year rollover, F4E-014
supplies the open-ended multi-team rule, F4E-022 supplies the did-not-play
predicate, and F4E-025 supplies the parser-contract registry recorded in the
artifact.

# Resolved artifact contract

- The artifact is generated on demand and is not committed. The build command
  requires an explicit `--output PATH`; callers will normally choose `reports/`,
  which is already ignored.
- Schema version 1 is a top-level integer and unknown versions are rejected.
- Entries use natural keys, never surrogate database IDs.
- Each `(basketball_reference_player_id, season_year)` entry has independent
  sets for regular aggregate tables, postseason aggregate tables, regular
  team-stint keys, and postseason team-stint keys. A team-stint key is
  `(team_code, table)`; the regular set may include roster.
- Did-not-play evidence is recorded separately for regular season and
  postseason. It suppresses only the matching aggregate expectation. It does
  not erase independently observed roster or team-stint expectations.
- The artifact records the current parser-contract identifiers from F4E-025.
- The cache fingerprint is SHA-256 over a canonical stream of each discovered
  source's cache-root-relative POSIX path and SHA-256 of its decompressed HTML,
  sorted by path. It records player-page and team-page counts separately.
- Any parsed season that produces no expectation and has no did-not-play
  explanation is written under `unexplained`; the build command writes the
  artifact and exits non-zero.

# Human decisions or resources

- None.

# Acceptance criteria

- A pure module under `src/nba_data/validation/` builds schema-version-1 coverage
  artifacts without importing database sessions, engines, ORM models, or HTTP
  clients.
- `uv run nba-data validate build-stats-coverage --output PATH` builds the
  artifact from `Settings.scraper_cache_dir`. It supports an explicit cache-root
  override for offline fixtures and refuses a missing root.
- Player pages are enumerated through the corrected shared discovery contract;
  team pages use the strict cache inventory contract. Unreadable, empty, or
  malformed candidates are reported and make the build fail.
- Expectations are classified from parsed source rows. Normalizer selection
  entries may be recorded as comparison evidence, but they are not the source
  of the expected key set; a disagreement is reported rather than cancelled.
- Regular aggregate selection follows the official single-team/multi-team rule,
  including any numeric marker of at least `2TM`. `TOT` never becomes an
  expectation.
- Regular roster and team-stint expectations come from team-season pages.
  Postseason aggregate and team-stint expectations come from player pages.
- F4E-022's shared did-not-play predicate is reused. Tests cover at least three
  observed reason strings, including the bare `Did not play -`, and prove the
  marker is season-type scoped.
- Tests prove a player-season can simultaneously carry regular and postseason
  expectations, and that a regular did-not-play marker can coexist with real
  postseason expectations.
- Fixture coverage includes a short player ID, a century-crossing season,
  `5TM`, `milleol01`-shaped real-row-plus-placeholder input, a traded regular
  season, and postseason team stints.
- Reordering source files or JSON entries does not change the fingerprint or
  semantic artifact. Changing a relative path or decompressed HTML does.
- Tests use checked-in miniature HTML fixtures only. They do not read the real
  `data/` directory, connect to PostgreSQL, or make network requests.

# Scope

- A coverage artifact builder and typed schema under `src/nba_data/validation/`.
- A `validate build-stats-coverage` CLI command.
- Cache enumeration/fingerprint helpers where needed.
- Offline fixtures, unit tests, and the two official-stats mapping documents.

# Out of scope

Reading or validating PostgreSQL, which is F4E-018. Repairing any row. Running a
backfill or acquisition. Creating a checked-in full-archive artifact or an
exceptions allowlist.

# Impact

Introduces the independent oracle consumed by F4E-018. It is cache-only and
read-only; no database schema, persisted data, scraper rate limit, or runtime API
behavior changes.

# Implementation notes

Keep the source-semantic classifier small and explicit. Sharing stable semantic
predicates such as `is_multi_team_marker` and F4E-022's did-not-play detector is
correct; sharing the normalizer's final row-selection result is not.

Write the JSON atomically after successful serialization. On classification
issues, preserve the diagnostic artifact but return a non-zero command exit so
automation cannot mistake it for a complete oracle.

# Durable knowledge updates

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — define cache-derived natural-key
  coverage and identify the two cache sources.
- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — record season-type-scoped
  did-not-play behavior and the player-page portions of the artifact.

# Review evidence

## Review round 1 fixes

The first review pass found five real defects, all fixed:

1. **High — malformed cache sources silently accepted.** `read_cached_gzip`
   (`scraping/player_page_cache.py`) now rejects content that does not look
   like an HTML document (matching `cache_inventory`'s own check) and catches
   `UnicodeDecodeError` alongside `OSError`, instead of letting it raise out of
   discovery before any artifact was written. `build_stats_coverage_artifact`
   now also reports a team-season-shaped filename with unparsable
   team/season metadata (`missing_metadata`) as a source issue, not only
   `invalid_or_unreadable`.
2. **High — a missing team code created a false aggregate expectation.**
   `_classify_aggregate`'s `real_rows` filter was missing the
   `parsed_team_code(row) is not None` guard the normalizer's own
   `_select_full_season_row` always applied, so a row with no team-code field
   at all (and no did-not-play marker) counted as "real" instead of falling
   through to `unexplained`.
3. **Medium — valid postseason data generated false disagreements.**
   `_compare_aggregate_with_normalizer` compared every `status="selected"`
   selection entry against the aggregate map, including postseason
   team-stint entries (`selected_real_team_postseason_row`) — for a
   single-team postseason, the same row generates *two* selection entries
   (one aggregate, one team-stint), and the team-stint one was wrongly read as
   "aggregate not selected". Now only the known aggregate-decision reasons are
   compared; a decision-irrelevant reason is skipped entirely, not counted as
   "not selected".
4. **Medium — the fingerprint was not sensitive to every decompressed-HTML
   change.** `_digest_of_cached_file` now hashes a fresh, unstripped read of
   the decompressed content instead of the already-`.strip()`-ed string
   `required_html`/`read_cached_gzip` return for parsing purposes.
5. **Medium-low — the purity boundary was not real.** `player_page_cache.py`
   imported `PLAYER_ID_PATTERN` from `scraping/player_page_acquisition.py`,
   which imports SQLAlchemy, ORM models, and the HTTP client — two hops from
   `stats_coverage.py`'s own clean import list, so the original purity test
   (checking only `stats_coverage.py`'s direct imports) missed it. Fixed by
   moving `PLAYER_ID_PATTERN`/`PLAYER_ID_MIN_LENGTH`/`PLAYER_ID_MAX_LENGTH`
   into a new dependency-free leaf, `domain/player_id.py` (matching
   `domain/team_codes.py`'s existing pattern), which both
   `player_page_acquisition.py` and `player_page_cache.py` now import from.
   Also converted `validation/__init__.py` to PEP 562 lazy attribute
   resolution, since eagerly importing `official_stats` there meant merely
   importing `nba_data.validation.stats_coverage` (a submodule of that same
   package) pulled in SQLAlchemy regardless of `stats_coverage.py`'s own
   imports — Python always runs a package's `__init__.py` first. Verified
   with a real subprocess import: `sys.modules` after `import
   nba_data.validation.stats_coverage` now contains no `sqlalchemy.*`,
   `httpx`, or `nba_data.db.*` entries at all.

7 new regression tests added for these (`test_stats_coverage_artifact.py`):
a transitive-import-graph purity checker (proven to catch finding 5 by
temporarily reintroducing the bug and confirming the test fails, then
restoring the fix), a not-HTML-content test, an invalid-UTF-8 test, a
`missing_metadata` team-page test, a missing-team-code test, a
single-team-postseason false-disagreement test (plus `disagreements == ()`
assertions added to two existing postseason tests), and a trailing-newline
fingerprint test.

## Review round 2 fixes

The second review pass found four more real defects, all fixed:

1. **High — truncated player gzip files crashed the build.**
   `read_cached_gzip`'s except clause caught `OSError`/`UnicodeDecodeError`
   but not `EOFError`, which is what a gzip stream truncated mid-decompression
   (trailing CRC/ISIZE bytes cut off) actually raises — it is a plain
   `Exception` subclass, not an `OSError` subclass. Added `EOFError` to the
   caught tuple so a truncated file is reported as unreadable, like any other
   malformed candidate, instead of crashing the whole build before any
   diagnostic artifact is written.
2. **High — error-page HTML produced a falsely complete artifact.** The
   doctype/`<html>`-prefix check in `read_cached_gzip` only rules out content
   that isn't HTML at all; it does not rule out real HTML (an error or
   interstitial page) that simply carries none of the supported stats tables.
   `build_stats_coverage_artifact` now checks, after parsing, whether a
   discovered page produced zero rows across every one of its supported
   tables (both season types for player pages, all tables for team-season
   pages) and reports that as an `invalid_or_unreadable` source issue instead
   of silently treating it as a legitimate zero-expectation page. No real
   Basketball Reference player or team-season page is this bare, so this
   cannot false-positive on genuine content.
3. **High-medium — malformed player-cache filenames stayed invisible.**
   `_scan_unreadable_player_source_issues` matched candidate filenames only
   against the strict `_PLAYER_CACHE_FILE_RE` (which also validates the digest
   as 16 hex characters), so a player-shaped filename with a malformed digest
   matched neither that regex nor anything else and vanished from the scan —
   unlike the equivalent team-season case, which `cache_inventory` reports as
   `missing_metadata` via its own looser "looks like a candidate" regex. Added
   the analogous `_PLAYER_CACHE_LIKE_FILE_RE` to `player_page_cache.py` and a
   second branch in the scanner: strict match but undiscovered ⇒
   `invalid_or_unreadable` (unchanged); loose match only ⇒ `missing_metadata`.
4. **Medium — the fingerprint still normalized some content changes.**
   `_digest_of_cached_file` read the decompressed content in text mode
   (`gzip.open(path, "rt", ...)`), which applies universal-newline translation
   (CRLF/CR → LF) invisibly — so a cached file differing only by line ending
   produced the same digest, contrary to the "SHA-256 of the decompressed
   HTML" contract. Now reads and hashes in binary mode (`"rb"`), so the digest
   reflects the literal decompressed bytes with no text-mode translation at
   all.

4 new regression tests added for these, each proven to have teeth by
temporarily reverting its corresponding fix, confirming the test fails with
exactly the reported symptom, then restoring the fix: a truncated-gzip test
(reproduces the raw `EOFError` traceback before the fix), an
error-page-with-no-tables test (reproduces `is_complete=True` with zero
entries and zero issues before the fix), a malformed-player-digest test
(reproduces the file vanishing from source issues before the fix), and a
CRLF-vs-LF fingerprint test (reproduces the identical-digest collision before
the fix).

## Automated validation

- Command: `uv run pytest tests/unit/test_stats_coverage_artifact.py`
  Result: 31 passed.
- Command: `uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py tests/unit/test_player_page_normalizer.py`
  Result: 157 passed.
- Command: `uv run pytest tests/unit`
  Result: 819 passed.
- Command: `uv run ruff check .`
  Result: All checks passed!
- Command: `uv run pytest`
  Result: 819 passed, 25 skipped (skips are the PostgreSQL integration lane, not run offline).
- Command: `uv run python scripts/validate_tasks.py`
  Result: Task validation passed.

## Manual happy path

1. Wrote `tests/fixtures/html/player_page_harden_regular_season.html` (an
   already-checked-in 2TM-trade fixture) into a scratch cache root at
   `basketball-reference/players-h-hardeja01.html-<hex>.html.gz`, using the
   real `HtmlCache.path_for_url` slug/digest scheme.
2. Ran `uv run nba-data validate build-stats-coverage --cache-root
   <scratch-cache> --output <scratch-out>/coverage.json`.
3. Read the written JSON.

Expected result: exit code 0; `counts.entries == 1`, `unexplained == []`,
`source_issues == []`; the one entry is `hardeja01`/`season_year=2021` with
all 8 `stats.player_season_*` tables in `regular_aggregate_tables` and no
team stints (none expected — team stints come only from team-season pages,
which the scratch cache had none of). Got exactly this. Full artifact
captured in the conversation transcript.

## Manual sad path

1. Ran `uv run nba-data validate build-stats-coverage --cache-root
   ./does-not-exist-f4e017 --output <scratch-out>/coverage2.json`.

Expected result: non-zero exit (Typer `BadParameter`, exit code 2), a clear
error naming the resolved absolute missing path and pointing at
`SCRAPER_CACHE_DIR`/the working directory, and no output file written. Got
exactly this — `coverage2.json` does not exist afterward.

Both scratch directories were deleted after verification; nothing under them
is part of this change.

## Known limitations

- F4E-027 ("extract the shared player-page backfill helpers") is narrowed by
  this card, not closed: the pure discovery contract (`resolve_player_cache_root`,
  `discover_player_cache_entries`, `discovery_status_for`, `read_cached_gzip`,
  `required_html`) now lives in the new `scraping/player_page_cache.py`, shared
  by both backfills and the new coverage builder. The postseason backfill still
  imports the private `_validate_inputs` from the regular-season backfill —
  that one remaining cross-import is F4E-027's real remaining scope; the
  backlog card's `read:` list may need a short update to match.
- The `disagreements` mechanism is exercised by every fixture test (all pass
  with `disagreements == ()`, including the postseason single-team case
  review round 1 caught as a false positive) but no test forces a *genuine*
  disagreement between the classifier and the normalizer, since the two are
  independently coded from the same shared predicates and are expected to
  agree whenever both are correct.
- Fingerprint stability under "reordering source files" is guaranteed by
  construction (paths are sorted before hashing) but has no dedicated test
  beyond the idempotency check already present.
