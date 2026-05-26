# Phase 4B - Controlled Raw HTML Backfill

Status: done
Phase ID: `phase-4b-controlled-raw-html-backfill`

## Goal

Create the controlled raw HTML acquisition path that can populate `HtmlCache`
with approved Basketball Reference pages before any offline database loading.

The target flow is:

`approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`

Phase 4B is an acquisition phase only. It may create planning, dry-run, and
cache-first runner behavior, but it must not parse for database loading, write
database rows, apply migrations, or run a historical full backfill.

## Preconditions

- `F4A-001` must be `done` in `tasks/feature-list.json` before this phase is
  made current.
- No task may be `approved` or `in_progress` when this phase is introduced as
  `proposed`.
- `F4B-001` was approved explicitly by the owner and closed as design-only
  work; later Phase 4B tasks must still not be auto-approved while this phase
  is `proposed`.

## Phase Tasks

- `F4B-001`: Design controlled raw HTML backfill manifest. Done.
- `F4B-002`: Add raw HTML backfill manifest dry-run validation. Done.
- `F4B-003`: Add sequential cache-first raw HTML acquisition runner. Done.
- `F4B-LIVE-001`: Run owner-approved raw HTML backfill pilot. Done.

## Allowed Work

- Design a manifest format for explicitly approved Basketball Reference URLs.
- Default the first real pilot to at most five team-season URLs.
- Support dry-run planning that reports URLs, page types, expected cache paths,
  and estimated live request counts without network access.
- Implement a cache-first acquisition runner that checks `HtmlCache` before any
  live request.
- Use `BasketballReferenceClient` for all live cache misses.
- Store raw HTML only as `.html.gz` through `HtmlCache`.
- Record acquisition summaries in progress and learning docs.
- Keep player-specific pages out of the initial pilot unless a later manifest
  task explicitly adds them.

## Disallowed Work

- Running live scraping without owner approval for the exact manifest.
- Concurrent live acquisition.
- Exceeding 10 requests/minute by default or 20 requests/minute ever.
- Full historical scraping.
- Database writes, SQLAlchemy migrations, or loader execution.
- Offline parse/normalize/validate runtime implementation.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.
- Proxy rotation, user-agent randomization, CAPTCHA bypass, or rate-limit
  evasion.

## Live Acquisition Rules

- Live acquisition is sequential and cache-first.
- Cache hits must make no live request.
- Each cache miss may make at most one live request.
- HTTP 429 stops the run through central client behavior.
- Every live run requires owner approval for the exact manifest.
- Pilot results must state how many URLs hit cache, missed cache, fetched live,
  failed, or were skipped.

## Done Criteria

- A reviewed manifest strategy exists.
- Dry-run validation can prove what would happen without contacting Basketball
  Reference.
- The acquisition runner is implemented and tested with fakes/mocks only.
- Any live pilot is explicitly approved, small, sequential, cache-first, and
  recorded.
- No DB writes, migrations, offline loading, API/frontend/OVR work, or
  historical full scrape occurred.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Handoff

Phase 4B hands cached `.html.gz` files to later phases. Phase 4 creates the
SQLAlchemy schema and idempotent loaders. Phase 4C then processes already
cached HTML offline and loads only validated normalized rows.

## Closure Summary

Phase 4B closed after `F4B-001`, `F4B-002`, `F4B-003`, and `F4B-LIVE-001`
were reviewed and marked `done`. The owner-approved two-URL pilot verified the
controlled path:

`approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`

No additional live acquisition, DB writes, migrations, offline loading,
API/frontend/OVR work, raw HTML deletion, or legacy/Peewee deletion was
approved during closure.
