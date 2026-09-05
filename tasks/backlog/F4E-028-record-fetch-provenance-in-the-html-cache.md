---
id: F4E-028
title: Record fetch provenance beside every newly cached page
areas:
  - scraping
  - documentation
priority: 40
depends_on: []
read:
  - src/nba_data/scraping/cache.py
  - src/nba_data/scraping/client.py
  - src/nba_data/scraping/team_season_pages.py
  - src/nba_data/scraping/backfill_manifest.py
  - src/nba_data/scraping/player_page_acquisition.py
  - docs/decisions/0003-cache-raw-html.md
  - docs/architecture/IMPACT_MAP.md
validation:
  - uv run pytest tests/unit/test_html_cache.py tests/unit/test_rate_limited_client.py tests/unit/test_team_season_pages.py tests/unit/test_backfill_manifest.py tests/unit/test_player_page_acquisition.py tests/unit/test_nba_team_season_acquisition.py
  - uv run pytest tests/unit/test_cache_inventory.py tests/unit/test_stats_coverage_artifact.py
  - uv run ruff check .
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Observing a sidecar written from a real Basketball Reference response would require an owner-approved live acquisition. This card is validated entirely offline with fake clients and tmp_path caches; it neither needs nor authorizes a live fetch.
  - No page already in data/raw/html/ is re-fetched, rewritten, or given a backfilled sidecar. The 3,326 existing files stay byte-identical.
---

# Goal

Give every page fetched **from now on** a sidecar recording when it was fetched,
what status the server answered, and which URL was finally served. Nothing
records any of that today, so the only surviving provenance is a filesystem
mtime that says when a file was *written* and does not survive a copy or an
archive extraction.

The 3,326 pages already cached get nothing. Their provenance is genuinely
unknown, and unknown is represented by the absence of a sidecar — never by a
guessed timestamp.

# Evidence and current state

## The body is all that is written

`HtmlCache.set` at [`cache.py:23-28`](../../src/nba_data/scraping/cache.py#L23-L28)
writes the gzip body and returns the path. No sidecar, no header, no index.
`path_for_url` at `:33-51` encodes *which URL* a file came from in the filename
and nothing about the fetch.

## Only the client sees the response, and it is usually not the writer

[`client.py:79-105`](../../src/nba_data/scraping/client.py#L79-L105) inspects
`response.status_code` for 429/5xx handling, follows redirects
(`follow_redirects=True` at `:39`), then returns `response.text` and drops both
facts. Nothing in `src/nba_data/scraping/` imports `datetime` for a fetch time;
the only date handling in the package is `parsedate_to_datetime` on a
`Retry-After` header at `:127`.

There are **three** `cache.set` writers, and the client is the least used:

- [`client.py:66`](../../src/nba_data/scraping/client.py#L66) — only when the
  client was constructed with a cache.
- [`team_season_pages.py:103`](../../src/nba_data/scraping/team_season_pages.py#L103)
- [`backfill_manifest.py:317`](../../src/nba_data/scraping/backfill_manifest.py#L317),
  and `player_page_acquisition.py:347` via `_write_html_to_cache_safely`.

Every CLI construction — [`main.py:260`](../../src/nba_data/cli/main.py#L260),
`:706`, `:830` — is `BasketballReferenceClient(settings)` with **no cache**. In
production the client never writes the cache at all; the callers do. So
provenance cannot simply be written inside `client.get`: the client must hand
its callers what it saw, and the callers must pass it to `cache.set`.

Both caller protocols declare only
`get(url, *, force_refresh: bool = False) -> str` — `BackfillClient` at
`backfill_manifest.py:26-28` and `PlayerPageAcquisitionClient` at
`player_page_acquisition.py:47-49`.

## A sidecar is invisible to every existing consumer

Every discovery path globs `*.html.gz` and matches the name against a regex that
requires that ending:

- [`cache_inventory.py:104`](../../src/nba_data/scraping/cache_inventory.py#L104)
- [`player_page_cache.py:97`](../../src/nba_data/scraping/player_page_cache.py#L97)
- [`stats_coverage.py:923`](../../src/nba_data/validation/stats_coverage.py#L923)
- [`recount_player_page_candidates.py:303`](../../scripts/recount_player_page_candidates.py#L303)
  (`players-*.html.gz`)
- [`offline_processor.py:381`](../../src/nba_data/scraping/offline_processor.py#L381)
  rejects an explicit path that does not end in `.html.gz`.

A file named `<page>.html.gz.meta.json` matches none of those globs, so no
discovery path, coverage scan, or backfill sees it without being changed. That
is why the sidecar wins over an index file or an in-stream header: zero blast
radius on the four filename regexes `IMPACT_MAP.md:41-47` protects.

## The acquisition path already has the write pattern to copy

`_write_html_to_cache_safely` at
[`player_page_acquisition.py:514-536`](../../src/nba_data/scraping/player_page_acquisition.py#L514-L536)
refuses to overwrite an existing file, writes to a `.tmp` sibling, reads it back
to verify, then `os.replace`s it. The sidecar write in that path must hold the
same line — `IMPACT_MAP.md:102` lists "never overwrite a cache file" as an
invariant of the approved-acquisition flow.

# Human decisions or resources

- [x] **1. Is fetch provenance worth recording at all?** Yes — for **audit**,
      not freshness: "when did we last see this page, and did the server
      actually answer 200?". These are static historical pages; nothing here
      implies a TTL, expiry, or re-fetch. (Owner, 2026-08-27.)
- [x] **2. Where does it live?** A **sidecar JSON file** next to each
      `.html.gz`. Not an index file (drifts from what it describes, and partial
      or concurrent writes become a correctness problem), not an in-stream
      header (would leave `HtmlCache.get` with two formats forever, since 3,326
      legacy files have no header). The `raw.raw_pages` option is gone:
      `F4E-020` drops the `raw` schema in revision `0008`, so a database record
      of the cache would now require a new migration and a new decision.
      (Owner, 2026-08-27.)
- [x] **3. What is recorded?** `fetched_at` (timezone-aware UTC), `http_status`
      (the status the client actually received), and `final_url` (the client
      follows redirects, so the URL served may not be the URL requested). No
      content hash — `stats_coverage.py:963-978` already fingerprints
      decompressed bytes on demand — and no user agent or scraper version.
      (Owner, 2026-08-27.)
- [x] **4. Does anything backfill provenance for the pages already cached?**
      **No.** Their provenance is unknown and stays unknown; a guessed timestamp
      is worse than nothing. This agrees with `F4E-020` decision 2, which
      records explicit NULL as the rule if a database record ever returns.
      (Owner, 2026-08-25 and 2026-08-27.)
- [x] **5. Must a cached page remain readable without its metadata?** Yes.
      Metadata is an **index, not an invariant**: `HtmlCache.get` and
      `HtmlCache.exists` behave identically whether or not a sidecar exists. A
      *missing* sidecar means "unknown". A *malformed* one is an error, so
      corruption is never silently reported as "never fetched".
      (Owner, 2026-08-27.)

# Acceptance criteria

## Cache

- `src/nba_data/scraping/cache.py` defines a frozen dataclass
  `CacheFetchMetadata` with `fetched_at: datetime` (timezone-aware),
  `http_status: int`, and `final_url: str`. Constructing one with a naive
  `fetched_at` raises `ValueError`.
- `HtmlCache.metadata_path_for_url(url)` returns the `path_for_url(url)` path
  with `.meta.json` appended to its filename, and `path_for_url` itself returns
  exactly what it returns today — a test asserts the `.html.gz` name is
  unchanged for a known URL.
- `HtmlCache.set(url, html, *, metadata: CacheFetchMetadata | None = None)`
  keeps its current call sites working unchanged. With `metadata`, it writes the
  sidecar as JSON containing `schema_version`, `fetched_at` (ISO-8601 with
  offset), `http_status`, and `final_url`. Without `metadata`, it writes no
  sidecar and **removes any existing one** for that URL, so a sidecar never
  describes a body it did not come from.
- `HtmlCache.get_metadata(url)` returns `None` when no sidecar exists, a
  `CacheFetchMetadata` when one does, and raises `CacheMetadataError` when the
  sidecar exists but is unreadable, is not JSON, or is missing a required field.
- `HtmlCache.get` and `HtmlCache.exists` return the same results with the
  sidecar present, absent, and corrupt. A test proves a page written before this
  card — a bare `.html.gz` with no sidecar — still reads, and reports its
  provenance as `None`.
- The sidecar is written atomically: temp sibling then `os.replace`, so a
  crashed write never leaves a half-written sidecar beside a good body.

## Client

- `BasketballReferenceClient` takes an injectable `now: Callable[[], datetime]`
  defaulting to `datetime.now(UTC)`, alongside the existing `sleeper` and
  `clock` seams. (`clock` is `time.monotonic` and is not a wall clock; it is not
  reused for this.)
- A new `fetch(url, *, force_refresh: bool = False) -> FetchResult` returns the
  HTML plus `metadata: CacheFetchMetadata | None`, which is `None` on a cache
  hit and populated on a live fetch from `response.status_code`,
  `str(response.url)`, and `now()`.
- `get()` keeps its exact current signature and return type and is a thin
  wrapper over `fetch`. No existing `client.get` call site changes behaviour.
- When the client owns a cache and performed a live fetch, it passes the
  metadata to `cache.set`. On a cache hit it does not write at all.
- Rate limiting, the 429 stop, the 5xx retries, `Retry-After` handling, and
  `RateLimitExceededError` are untouched; their existing tests pass unmodified.

## Callers that own the cache write

- `BackfillClient` and `PlayerPageAcquisitionClient` gain `fetch`, and the fake
  clients in `tests/unit/test_backfill_manifest.py`,
  `tests/unit/test_nba_team_season_acquisition.py`, and
  `tests/unit/test_player_page_acquisition.py` implement it.
- `team_season_pages.fetch_basketball_reference_html`,
  `backfill_manifest.acquire_backfill_manifest`, and `player_page_acquisition`'s
  acquisition loop obtain metadata from `fetch` and pass it to their
  `cache.set` / `_write_html_to_cache_safely` call, so a page written through
  any of the three carries provenance.
- `_write_html_to_cache_safely` refuses to overwrite an existing **sidecar** for
  the same reason it refuses to overwrite an existing body, and leaves neither
  file behind when it raises. A test covers a pre-existing sidecar with no body.
- Where a caller previously re-wrote a body the client had already cached, the
  page still ends with exactly one body and one sidecar, and the second write
  does not delete the sidecar the first one wrote.

## Nothing else moves

- `uv run pytest tests/unit/test_cache_inventory.py tests/unit/test_stats_coverage_artifact.py`
  passes with sidecars present in the fixture cache root — a test adds a sidecar
  beside a discovered page and asserts discovery counts, coverage counts, and
  reported source issues are identical to the run without it.
- `grep -rn "meta.json" src/ scripts/` shows the sidecar is written and read only
  in `cache.py` and the fetch/acquisition call sites — no discovery, parsing, or
  loading path consumes it.
- No file under `data/raw/html/` is modified: the card's changes are exercised
  only against `tmp_path` caches.

## Documentation

- `docs/decisions/0003-cache-raw-html.md` records the amendment: the cache is a
  body plus an optional provenance sidecar; the sidecar is an index, not an
  invariant; pages fetched before this card have none and are never backfilled.
- `docs/architecture/SYSTEM_DESIGN.md:52` describes both artifacts instead of
  only `.html.gz`.
- `docs/architecture/IMPACT_MAP.md` names the sidecar in the scraping section
  and states that it is deliberately outside the `*.html.gz` glob the four
  discovery regexes depend on.

# Scope

`src/nba_data/scraping/cache.py`, `client.py`, `team_season_pages.py`,
`backfill_manifest.py`, `player_page_acquisition.py`; the unit tests listed in
`validation:`; `docs/decisions/0003-cache-raw-html.md`,
`docs/architecture/SYSTEM_DESIGN.md`, `docs/architecture/IMPACT_MAP.md`.

# Out of scope

Re-fetching any page, and any live acquisition. Backfilling provenance for the
3,326 cached files. Cache eviction, expiry, TTL, or any refresh policy — those
can only be designed after provenance exists, and folding them in here would
make the card unstartable. Any database table for cache metadata; `F4E-020` owns
the `raw` schema and drops it. `HtmlCache.path_for_url`'s output shape and the
four filename regexes that depend on it. Acquisition report shapes — putting
provenance into the JSON reports is a separate question. The live-scraping
approval interlock: the `--owner-approved` flags, manifest schema, and guards
are read and preserved, never relaxed to make plumbing easier.

# Impact

- **Scraping:** every future live fetch writes a second small file per page.
  After an approved acquisition of *n* pages, `data/raw/html/` holds *n* new
  sidecars alongside *n* new bodies.
- **Discovery and coverage:** unchanged by construction, and pinned by a test
  that puts a sidecar in a fixture cache root.
- **Client API:** `get` is unchanged; `fetch` is additive. Two Protocols gain a
  method, so three test fakes need it.
- **Acquisition reports:** unchanged. `PlayerPageDryRunEntry` and its
  acquisition counterparts keep carrying `cache_path`, `cache_status`, and
  counts.
- **`F4E-020`:** independent. It drops the `raw` schema; this writes files. They
  can land in either order; neither blocks the other.

# Implementation notes

Read `F4E-020` first for the raw-schema disposition — its decision 2 is the rule
this card's decision 4 agrees with.

`HtmlCache.path_for_url` must return exactly what it returns today.
`cache_inventory.py`, both player-page backfills, the stats-coverage scan, and
the acquisition dry-runs all derive their view of the archive from that shape,
and `F4E-012` was a card about exactly this contract drifting.

Prefer widening `set` with a keyword-only `metadata` over adding a second write
method: one writer means one place where "body and sidecar disagree" can be
prevented.

The `now` seam matters for tests — asserting against a real `datetime.now(UTC)`
is how a flaky test gets written. Follow the existing `sleeper`/`clock`
injection style in the client's constructor. `datetime.now(UTC)` with
`from datetime import UTC, datetime` is the repo's existing form
(`db/repositories/stats.py:5,1007`). Do not use `utcnow`.

When touching `player_page_acquisition.py`, treat everything around the approval
guards as read-only structure: the acquisition loop can gain a metadata
argument, but no guard, flag, or manifest check changes shape.

# Durable knowledge updates

- `docs/decisions/0003-cache-raw-html.md` — amend: the cache is a body plus an
  optional provenance sidecar, written forward only.
- `docs/architecture/SYSTEM_DESIGN.md` — the cache contract now has two
  artifacts.
- `docs/architecture/IMPACT_MAP.md` — the sidecar exists and is deliberately
  outside the `*.html.gz` glob.

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
