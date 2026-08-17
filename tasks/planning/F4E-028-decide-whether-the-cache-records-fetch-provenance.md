---
id: F4E-028
title: Decide whether the HTML cache records fetch provenance
areas:
  - planning
  - scraping
  - database-schema
priority: 40
depends_on: []
read:
  - src/nba_data/scraping/cache.py
  - src/nba_data/scraping/client.py
  - src/nba_data/db/models/raw.py
validation:
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Decide whether a cached page keeps any record of **when it was fetched and what
the server answered**. Nothing records either today, which is why `F4E-020` has
to choose a fiction for `fetched_at` when reconstructing `raw.raw_pages` from the
archive. This card is about the pages fetched from now on; `F4E-020` is about the
ones already on disk.

# Evidence and current state

`HtmlCache.set` at
[`cache.py:23-28`](../../src/nba_data/scraping/cache.py#L23-L28) writes the gzip
body and returns the path. There is no sidecar file, no header block, no index.
`path_for_url` at `:33-51` derives the filename from the URL and a SHA-256
prefix, so the path encodes *which URL* a file came from and nothing about the
fetch.

The client has both facts and drops them.
[`client.py:56-67`](../../src/nba_data/scraping/client.py#L56-L67) calls
`self.cache.set(url, html)` with only the body; `_get_from_network` at `:79-105`
inspects `response.status_code` for 429 and 5xx handling and then returns
`response.text`. Nothing in `src/nba_data/scraping/` imports `datetime` for a
fetch time — the only date handling in the whole package is
`parsedate_to_datetime` parsing a `Retry-After` header at `:127`.

The acquisition reports do not close the gap either. `PlayerPageDryRunEntry`
(`player_page_acquisition.py:94-102`) and its acquisition counterparts carry
`cache_path`, `cache_status`, and counts — no timestamp and no HTTP status. The
dates in `reports/` filenames were typed by the operator.

So the only surviving provenance is the filesystem mtime, which records when the
file was last **written**, not when the page was **fetched**, and which does not
survive a copy, restore, or archive extraction.

`raw.raw_pages` has columns waiting for exactly this data — `http_status` and
`fetched_at` at [`raw.py:26-28`](../../src/nba_data/db/models/raw.py#L26-L28) —
and `fetched_at` carries `server_default=func.now()`, so a naive insert stamps
the time of the *backfill*.

# Relationship to F4E-020

`F4E-020` decides the fate of the `raw` schema, and its decision 2 asks what
`http_status` and `fetched_at` should be **for rows reconstructed from the
existing cache**: NULL, mtime, or a sentinel. That question exists because this
one was never asked.

The two are separable — a decision to capture provenance going forward does not
decide what to do with 2,551 pages already on disk, and vice versa — but they
share a subject. **If `F4E-020` is answered first and its answer settles this,
close this card as absorbed rather than implementing it twice.**

# Human decisions or resources

- [ ] **1. Is fetch provenance worth recording at all?** The pages are static
      historical statistics; a 2003-04 box score does not change. The argument
      for recording it is cache invalidation and audit ("when did we last see
      this page, and did the server actually answer 200?"), not data freshness.
      Say which of those you want, or decide that neither justifies the cost.
- [ ] **2. If yes, where does it live?** A sidecar `.meta.json` next to each
      `.html.gz`, a header line inside the gzip stream, a single index file per
      cache root, or `raw.raw_pages` rows written at fetch time. Note that the
      fourth option makes the scraper depend on the database, which nothing in
      the acquisition path does today.
- [ ] **3. What is recorded?** Candidates: fetched-at timestamp, HTTP status,
      final URL after redirects (the client follows them), content length,
      content hash, and the scraper version or user agent. More fields mean more
      to keep correct; pick the smallest set that answers question 1.
- [ ] **4. Does anything backfill provenance for the 2,551 pages already
      cached?** The honest answer for those is "unknown", and writing a guessed
      timestamp is worse than a NULL. If the answer is "no", say so explicitly so
      a future card does not invent one — and confirm it agrees with whatever
      `F4E-020` decides.
- [ ] **5. Must a cached page remain readable without its metadata?** If a
      sidecar is lost or was never written, does `HtmlCache.get` still return the
      body, or is that an error? This decides whether metadata is an index or an
      invariant.

# Acceptance criteria

To be written once the decisions above are made. Whatever they are, an
implementation card must satisfy:

- The cache-first read path keeps working against every page already in
  `data/raw/html/` without re-fetching anything.
- No approved acquisition is required to answer any of the questions above.
- A page whose provenance is genuinely unknown is represented as unknown, never
  as a plausible-looking value.

# Scope

To be set when the card is prepared. Expected: `src/nba_data/scraping/cache.py`,
`src/nba_data/scraping/client.py`, their tests, and possibly
`src/nba_data/db/models/raw.py` with a migration if decision 2 chooses the
database.

# Out of scope

Re-fetching any page. Any live acquisition. The fate of `raw.scraper_runs` and
`raw.scraper_requests`, which `F4E-020` decision 3 owns. Cache eviction, expiry,
or a TTL policy — those are consequences that can only be designed after
provenance exists, and folding them in here would make the card unstartable.

# Impact

If provenance is adopted, every future acquisition writes something extra per
page, and `HtmlCache` gains a second on-disk artifact shape that
`cache_inventory.py` and both backfill discovery paths must ignore or understand.
That blast radius is a real input to decision 2: a sidecar file lands in the same
directories the discovery globs walk.

# Implementation notes

Read `F4E-020` before answering. If its decisions are made first, this card may
have nothing left to decide.

Whatever is chosen must not change what `HtmlCache.path_for_url` returns.
`cache_inventory.py`, both player-page backfills, and the acquisition dry-runs
all derive their view of the archive from that path shape, and `F4E-012` was a
card about exactly that contract drifting.

# Durable knowledge updates

- `docs/decisions/0003-cache-raw-html.md` — an ADR amendment if provenance is
  adopted; the current ADR describes the cache as the body only.
- `docs/architecture/SYSTEM_DESIGN.md` — the cache contract, if it changes.

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
