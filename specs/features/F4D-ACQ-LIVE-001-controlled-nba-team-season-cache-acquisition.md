# F4D-ACQ-LIVE-001 - Controlled NBA Team-Season Cache Acquisition

## Goal

Acquire missing NBA team-season pages from the reviewed Phase 4D-A manifest into
raw `HtmlCache` as `.html.gz` files.

This is the only Phase 4D-A task allowed to contact Basketball Reference, and
only after explicit owner approval for the exact manifest and an execution flag.

## Functional Requirements

- Refuse to run without explicit owner approval and an execution flag.
- Accept only the approved manifest from `F4D-ACQ-001`.
- Allow only URLs matching `/teams/{TEAM}/{YEAR}.html`.
- Check `HtmlCache` before any network request.
- Skip existing cache hits without network requests.
- Fetch only missing cache entries.
- Store fetched HTML only through `HtmlCache` as `.html.gz`.
- Produce an acquisition report with cache hits, fetched, skipped, failed, and
  rate-limited URLs.
- Be resumable and idempotent.

## Acquisition Policy

- Default rate limit is 10 requests/minute.
- Configurable maximum for this phase is 12 requests/minute.
- Absolute hard cap is 20 requests/minute.
- Stop immediately on HTTP 429 and report partial results.
- Async is allowed only with bounded concurrency and one global rate limiter.
- Retry/backoff is allowed only for safe transient failures and must not bypass
  the global rate limiter.
- Use Sports Reference policy references when implementing or reviewing:
  `https://www.sports-reference.com/bot-traffic.html` and
  `https://www.sports-reference.com/data_use.html`.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4D-ACQ-LIVE-001-controlled-nba-team-season-cache-acquisition.md`.
- The command refuses to run without explicit owner approval and an execution
  flag.
- Only approved manifest URLs matching `/teams/{TEAM}/{YEAR}.html` are
  eligible.
- Existing cache hits are skipped without network requests.
- Only missing cache entries are fetched and written as `.html.gz` through
  `HtmlCache`.
- Default rate limit is 10 requests/minute.
- Configurable max for this phase is 12 requests/minute.
- Hard cap remains 20 requests/minute.
- Async, if implemented, uses bounded concurrency and one global rate limiter.
- HTTP 429 stops the run immediately and reports partial results.
- The command is resumable and idempotent.
- The report includes cache hits, fetched, skipped, failed, and rate-limited
  URLs.
- No database writes, parser/load/backfill execution, API/frontend/OVR/ranking/
  similarity/recommendations/ML work, or non-team-season acquisition is
  introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Running without owner approval.
- Refreshing cache hits.
- Non-NBA pages.
- Player pages, boxscores, schedules, shot charts, or game logs.
- Database writes.
- Parser/load/backfill execution.
- API, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML work.
