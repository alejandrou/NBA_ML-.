# ADR 0004 - Rate Limited Scraping

## Status

Accepted

## Context

Sports Reference can block excessive traffic.

## Decision

Use a central rate-limited client with 10 requests/minute default and 20 requests/minute maximum.

Manual live acquisition smoke tests must be cache-first and must use
`BasketballReferenceClient` with `HtmlCache`. A smoke test defaults to 10
requests/minute, must never exceed 20 requests/minute, and must stop safely on
HTTP 429 through the central client behavior.

Do not use concurrent live scraping for smoke tests. Live smoke tests validate
only the acquisition/cache/parser boundary for an approved page; normal parser
and refactor correctness is validated offline.

## Consequences

Scraping is slower but safer and easier to audit.

## Alternatives Considered

- Per-scraper sleeps: inconsistent and easy to bypass.
- High concurrency: unsafe and against project rules.
