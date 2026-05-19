# ADR 0006 - Separate Scraper API Web

## Status

Accepted

## Context

The future system needs batch scraping, API access, and a web UI.

## Decision

Keep scraping jobs, API, and frontend as separate responsibilities.

## Consequences

The API will never scrape live. The frontend will consume API data only.

## Alternatives Considered

- API-triggered live scraping: risky and slow.
- Frontend direct DB access: unsafe and tightly coupled.
