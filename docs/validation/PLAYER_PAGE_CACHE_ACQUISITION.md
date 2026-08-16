# Player Page Cache Acquisition

How to acquire Basketball Reference player pages into `HtmlCache` safely.

This is a **procedure**, not a record of a past run. Player-page acquisition is
incomplete and resumable, so the durable knowledge is how to run it, not what one
run returned. (The team-season equivalent,
`docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md`, is the opposite: a
one-off record of a run that cannot be reproduced.)

These rules were the durable half of a retired feature spec, recoverable at
`git show main:specs/features/F4E-010-player-page-cache-acquisition.md`.

**Every acquire step contacts Basketball Reference and therefore needs the user's
direct, current instruction. No task card authorizes it.**

## What this acquires

- The manifest is built from `core.players.basketball_reference_player_id`, never
  from a hand-written list.
- It may be filtered by exact `basketball_reference_player_id`, and by inclusive
  season-year bounds through `core.player_seasons`.
- The manifest is deterministic for a given database state and set of filters.
- URLs are only ever
  `https://www.basketball-reference.com/players/{initial}/{player_id}.html`.

## Preconditions

- PostgreSQL is up and `core.players` is populated. An empty catalog yields an
  empty manifest, not an error.
- `SCRAPER_USER_AGENT` is a real contact address.
- The cache root is the one you intend. `Settings.scraper_cache_dir` defaults to
  the **relative** `data/raw/html`, so it resolves against the process working
  directory — start from the repository root, or set `SCRAPER_CACHE_DIR`
  explicitly. Pointing at the wrong root is silent: you get cache misses and a
  full re-fetch.

## Plan first, always

```bash
uv run nba-data acquisition dry-run-player-pages
uv run nba-data acquisition dry-run-player-pages --start-year 2000 --end-year 2025
uv run nba-data acquisition dry-run-player-pages --limit 5 --output reports/player-pages-dry-run.json
```

The dry run creates no live client, makes no request, and writes no database
rows. Read the cache hits, the missing entries, and the estimated fetch count
before asking for approval. Estimated fetches ÷ 10 is the minimum number of
minutes the real run will take.

## Acquire

```bash
uv run nba-data acquisition acquire-player-pages \
  --owner-approved --execute-approved-manifest \
  --limit 25 --output reports/player-pages-<yyyymmdd>.json
```

Both flags are required. With either missing the command prints

```text
Refusing acquisition without --owner-approved and --execute-approved-manifest
```

and exits 1 — before it builds a client or opens a database engine. Never
rename, remove, weaken, or bypass that interlock; it is the runtime safety gate
described in `AGENTS.md`.

## Rate and safety rules

- Cache first: an existing cache entry never triggers a live request.
- Never overwrite an existing cache file.
- Sequential only. No concurrency against Basketball Reference.
- At most 10 requests/minute (`PLAYER_PAGE_MAX_REQUESTS_PER_MINUTE`); the global
  hard cap is 20; at least 6 seconds between requests.
- Honor `Retry-After`.
- Stop immediately on HTTP 429 or any failed fetch, and emit a partial JSON
  report. The client is constructed with `max_429_retries=0` so a 429 stops the
  run instead of sleeping through it.
- Validate that fetched content is non-empty and HTML-shaped before storing it.
- Acquisition writes no database rows. Manifest planning writes no database rows.
- The player-page regular-season and postseason loaders stay **cache-only** and
  are never part of this procedure.

## Resume

Rerun the same command. Previously cached pages report as cache hits and cost no
request; only the gap is fetched. Keep every JSON report under `reports/` —
`reports/` is never committed.

## Report fields

`total_players`, `cache_hits`, `fetched`, `failures`, `live_request_count`, and
per-entry results. Compare `live_request_count` against the dry run's estimate;
a large gap means the cache root or the filters were not what you expected.

## Player-id contract

Acquisition and offline discovery accept the same 6-10 character player ids.
`PLAYER_ID_PATTERN` in `scraping/player_page_acquisition.py` is the single source
of truth; `_PLAYER_CACHE_FILE_RE` in `scraping/offline_player_stats_backfill.py`
imports that fragment instead of restating a range, so the two ends cannot drift
apart again. F4E-012 closed the earlier mismatch, where discovery matched only
8-10 characters and 36 acquired pages were cached and never processed.

A missing cache root is an error, not an empty result: both player backfills
raise `PlayerCacheRootNotFoundError` naming the resolved absolute path. An
existing root with no matching page still returns zero entries but reports
`discovery_status: "no_matching_pages"`.

## Related

- `docs/architecture/IMPACT_MAP.md` — the player-page acquisition flow and its
  cross-cutting couplings
- `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md` — the completed
  team-season acquisition record
- ADR 0003 (cache raw HTML), ADR 0004 (rate-limited scraping)
