# ADR 0003 - Cache Raw HTML

## Status

Accepted

## Context

Scraping should avoid duplicate downloads and preserve source pages for parser tests.

## Decision

Store raw HTML compressed on disk as `.html.gz` and store metadata in PostgreSQL later.

## Consequences

The local filesystem is the Phase 1 storage target. S3/R2 can be added later.

## Alternatives Considered

- Store full HTML in PostgreSQL: searchable but heavy.
- No raw cache: wastes requests and reduces reproducibility.
