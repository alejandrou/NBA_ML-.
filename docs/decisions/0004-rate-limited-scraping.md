# ADR 0004 - Rate Limited Scraping

## Status

Accepted

## Context

Sports Reference can block excessive traffic.

## Decision

Use a central rate-limited client with 10 requests/minute default and 20 requests/minute maximum.

## Consequences

Scraping is slower but safer and easier to audit.

## Alternatives Considered

- Per-scraper sleeps: inconsistent and easy to bypass.
- High concurrency: unsafe and against project rules.
