# Current Phase

Phase ID: `phase-4d-full-offline-database-preparation`
Status: `approved`

## Phase 4D - Full Offline Database Preparation / Backfill Readiness

## Goal

Prepare the real local PostgreSQL database from cached Basketball Reference
NBA team-season HTML before future read-only API work. Phase 4D now starts with
Phase 4D-A, a controlled cache acquisition subphase that prepares raw
`HtmlCache` coverage for Basketball Reference season end years 2000 through
2025.

The active Phase 4D-A boundary is:

```text
approved NBA team-season URL manifest -> cache-first acquisition -> HtmlCache .html.gz
```

No HTML may be fetched during this planning/docs checkpoint.

## Transition State

- Phase 4C is closed after `F4C-001`, `F4C-002`, and `F4C-003` were reviewed
  and marked `done`.
- Phase 4D is approved as the pre-API database preparation phase.
- Phase 4D-A has been inserted before cache inventory, processing, loading, and
  validation work.
- `F4D-ACQ-001` is `ready` as the first Phase 4D-A task.
- `F4D-ACQ-LIVE-001`, `F4D-ACQ-002`, `F4D-001`, `F4D-002`, `F4D-003`, and
  `F4D-004` remain `pending`.
- No Phase 4D-A or Phase 4D implementation has started.

## Phase Tasks

- `F4D-ACQ-001`: Generate NBA team-season URL manifest and dry-run plan.
- `F4D-ACQ-LIVE-001`: Run owner-approved controlled NBA team-season cache
  acquisition.
- `F4D-ACQ-002`: Review acquisition report and cache coverage handoff.
- `F4D-001`: Cached HTML inventory.
- `F4D-002`: Full offline backfill command.
- `F4D-003`: Data quality validation checks.
- `F4D-004`: API-ready database readiness documentation.

## Current Guardrails

- NBA only.
- Team-season pages only.
- Basketball Reference season end years 2000 through 2025 only.
- The acquisition manifest must contain exactly 775 unique URLs.
- Only `/teams/{TEAM}/{YEAR}.html` URLs are allowed.
- Do not fetch HTML until `F4D-ACQ-LIVE-001` receives explicit owner approval
  and uses an execution flag.
- Do not run live scraping or contact Basketball Reference in `F4D-ACQ-001`.
- Do not refresh cache hits.
- Do not write database rows, parse, load, backfill, or run data quality checks
  during Phase 4D-A acquisition tasks.
- Do not implement API endpoints, frontend pages, generated metrics, OVR,
  ranking, similarity, recommendations, or ML work.
- Do not create a branch, commit, push, or open a PR without explicit owner
  approval.

## Acquisition Policy

- Default rate limit: 10 requests/minute.
- Phase-configurable maximum: 12 requests/minute.
- Absolute hard cap: 20 requests/minute.
- Stop immediately on HTTP 429 and report partial results.
- Async is allowed only with bounded concurrency and a global rate limiter.
- Use retry/backoff only for safe transient failures without bypassing rate
  limits.
- Sports Reference policy references:
  `https://www.sports-reference.com/bot-traffic.html` and
  `https://www.sports-reference.com/data_use.html`.

## Next Safe Action

Implement `F4D-ACQ-001` only after explicit owner approval. The task may
generate and dry-run the approved URL manifest, but must not fetch HTML, write
`.html.gz` files, write database rows, parse, load, backfill, or contact
Basketball Reference.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4d-full-offline-database-preparation.md`
- `specs/features/F4D-ACQ-001-nba-team-season-manifest.md`
- `specs/features/F4D-ACQ-LIVE-001-controlled-nba-team-season-cache-acquisition.md`
- `specs/features/F4D-ACQ-002-acquisition-report-and-cache-coverage-review.md`
- `specs/features/F4D-001-cached-html-inventory.md`
- `tasks/feature-list.json`
