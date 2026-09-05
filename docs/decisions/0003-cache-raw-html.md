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

## Consequences

The local filesystem is the Phase 1 storage target. S3/R2 can be added later.
There is no database index of cached pages.

A metadata table should return only if it has a defined consumer, is populated
at fetch time with real provenance rather than reconstructed values, and has an
explicit consistency contract with the filesystem cache. Reintroducing one
would require a new schema decision and migration.

## Alternatives Considered

- Store full HTML in PostgreSQL: searchable but heavy.
- No raw cache: wastes requests and reduces reproducibility.
