# ADR 0016 - Live vs Offline Validation

## Status

Accepted

## Context

Legacy scraper consolidation needs confidence that parser and adapter behavior
still produces DB-compatible roster, totals, and advanced outputs. That
correctness can be tested from fixed HTML because parsers should read HTML
strings and should not depend on live network state.

The project also needs a narrow way to prove that acquisition, cache storage,
and parser shape still work against one approved live page without turning
normal validation into scraping.

## Decision

Use offline legacy-vs-new parity tests as the correctness gate for parser and
adapter refactors. These tests use frozen HTML fixtures or approved cached HTML
copied into test fixtures, compare legacy outputs against the consolidated
parser/adapter, and run fully offline in unit tests and CI.

Keep live acquisition smoke tests manual and gated. A live smoke test may cover
at most one owner-approved Basketball Reference team-season URL, must use
`BasketballReferenceClient` and `HtmlCache`, must be cache-first, and must make
at most one live request on cache miss.

The live smoke test validates acquisition, cache, and parser shape only. It
must not assert exact long-term statistical equality, write to the database, or
trigger historical scraping.

Concurrency policy remains governed by ADR 0015: no concurrent live scraping;
bounded concurrency is allowed only for already-cached local HTML in future
approved tasks.

## Consequences

Normal validation remains deterministic and offline. Live checks stay small,
auditable, and owner-approved, while still giving a practical safety check for
the acquisition/cache/parser boundary.

## Alternatives Considered

- Validate parser refactors with live pages in CI: rejected because CI must not
  contact Basketball Reference.
- Assert exact live-page statistics in smoke tests: rejected because live pages
  can change and the smoke test is for acquisition and shape only.
- Reuse live async fan-out as validation: rejected because live acquisition is
  sequential, cache-first, and rate-limited by project policy.
