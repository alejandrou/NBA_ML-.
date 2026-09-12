# ADR 0003 - Cache Raw HTML

## Status

Accepted

## Context

Scraping should avoid duplicate downloads and preserve source pages for parser tests.

## Decision

Store raw HTML compressed on disk as `.html.gz`. The filesystem cache plus the
JSON reports in `reports/` are the source of truth for cached source material.

The unpopulated `raw` PostgreSQL schema was dropped by revision
`0008_drop_raw_schema`. This supersedes the earlier intention to store cache
metadata in PostgreSQL later.

### Amendment (F4E-028): a cache entry is a body plus an optional sidecar

A cached page is one gzip body and, optionally, one provenance sidecar named
`<body>.html.gz.meta.json` beside it, holding `schema_version`, `fetched_at`
(timezone-aware, ISO-8601 with offset), `http_status`, and `final_url`. That is
audit provenance — "when did we last see this page, and did the server actually
answer 200?" — not freshness. These are static historical pages: nothing here
implies a TTL, an expiry, or a re-fetch policy.

The sidecar is an **index, not an invariant**. `HtmlCache.get` and
`HtmlCache.exists` behave identically whether or not one is present. A missing
sidecar means "provenance unknown"; a malformed one raises
`CacheMetadataError`, so corruption is never silently reported as "never
fetched". A sidecar whose `schema_version` is not the one this reader produces
is malformed by the same rule: it is refused rather than reinterpreted as
version 1, matching how `validation/stats_coverage.py` treats its own artifact
version.

Provenance is recorded **forward only**. The 3,326 pages cached before this
amendment have no sidecar and are never backfilled with one: their provenance is
genuinely unknown, and a guessed timestamp is worse than nothing. This matches
`F4E-020`'s rule that an absent fact is recorded as explicitly absent.

The sidecar deliberately sits outside the `*.html.gz` glob that every discovery
path uses, so it has zero blast radius on the filename regexes those paths
re-derive from `HtmlCache.path_for_url`. No content hash is stored:
`validation/stats_coverage.py` already fingerprints decompressed bytes on
demand.

## Consequences

The local filesystem is the Phase 1 storage target. S3/R2 can be added later.
There is no database index of cached pages.

Every page fetched from now on writes a second small file. After an approved
acquisition of *n* pages, the cache holds *n* new bodies and *n* new sidecars.
Provenance for the archive is therefore permanently split: pages fetched before
`F4E-028` report `None`, pages fetched after it report a real fetch.

A metadata table should return only if it has a defined consumer, is populated
at fetch time with real provenance rather than reconstructed values, and has an
explicit consistency contract with the filesystem cache. Reintroducing one
would require a new schema decision and migration.

## Alternatives Considered

- Store full HTML in PostgreSQL: searchable but heavy.
- No raw cache: wastes requests and reduces reproducibility.
