# ADR 0015 - Live vs Offline Concurrency

## Status

Accepted

## Context

Basketball Reference acquisition is constrained by external rate limits, not by
local CPU or parser throughput. The project now has a central
`BasketballReferenceClient`, `HtmlCache`, and pure cached HTML parser flow.
Future controlled backfill must preserve that boundary.

## Decision

Live Basketball Reference acquisition remains sequential and cache-first by
default. The project default remains 10 requests/minute, and the absolute max
remains 20 requests/minute.

Live concurrency is disabled by default because external rate limits are the
bottleneck. Async or concurrent processing is allowed only after HTML is cached
locally, and any offline cached HTML processing must use bounded parallelism in
a later approved task.

DB loading should prefer batch/idempotent upserts over direct per-row writes.

No proxy rotation, user-agent randomization, CAPTCHA bypass, or rate-limit
evasion is allowed.

## Consequences

Controlled backfill remains slower but auditable and respectful. Offline parsing
and validation can become faster later without increasing live request pressure.

## Alternatives Considered

- Live async fan-out: rejected because it bypasses the spirit of the project
  rate-limit policy.
- Per-scraper sleeps: rejected because sleeps are inconsistent and duplicate
  policy in multiple places.
- Proxy or user-agent rotation: rejected because it is rate-limit evasion.
