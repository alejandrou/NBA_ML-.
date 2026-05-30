# F4D-ACQ-LIVE-001 - Controlled NBA Team-Season Cache Acquisition

## Goal

Acquire missing NBA team-season pages from the reviewed Phase 4D-A manifest into
raw `HtmlCache` as `.html.gz` files.

This is the only Phase 4D-A task allowed to contact Basketball Reference, and
only after explicit owner approval for the exact manifest and an execution flag.

## Functional Requirements

- Refuse to run without explicit owner approval and an execution flag.
- Accept only the approved manifest from `F4D-ACQ-001`.
- Require explicit `START_YEAR END_YEAR` arguments for live acquisition.
- Allow any inclusive subset inside the reviewed 2000-2025 catalog.
- Reject ranges outside 2000-2025 until a reviewed historical catalog exists.
- Verify the deterministic full manifest ID and exactly 775 entries before
  creating the live client.
- Allow only URLs matching `/teams/{TEAM}/{YEAR}.html`.
- Check `HtmlCache` before any network request.
- Skip existing cache hits without network requests or cache overwrite.
- Fetch only missing cache entries.
- Use only `BasketballReferenceClient` for production HTTP access.
- Validate fetched content is non-empty and HTML-shaped before storage without
  parsing tables.
- Store fetched HTML only through `HtmlCache` as `.html.gz`.
- Write cache files safely so failed writes do not leave partial or corrupt
  final `.html.gz` files.
- Produce an acquisition report with cache hits, fetched, skipped, failed, and
  rate-limited URLs, including per-entry index, team, season, URL, cache path,
  status, and error details.
- Include `stopped_reason` and `stopped_at_entry` when acquisition stops early.
- Print the acquisition report as JSON to stdout.
- Optionally write the same JSON report to `--output`.
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
- The live command requires explicit start and end year arguments.
- Valid live ranges may be any inclusive subset inside 2000-2025.
- Invalid live ranges fail before creating a live client.
- The command verifies manifest ID `nba-team-season-2000-2025` and the full
  775-entry manifest before creating a live client.
- Only approved manifest URLs matching `/teams/{TEAM}/{YEAR}.html` are
  eligible.
- Existing cache hits are skipped without network requests or overwrites.
- Only missing cache entries are fetched and written as `.html.gz` through
  `HtmlCache`.
- Fetched content must be non-empty and HTML-shaped before storage.
- Cache writes do not leave partial or corrupt final `.html.gz` files on
  failure.
- Default rate limit is 10 requests/minute.
- Configurable max for this phase is 12 requests/minute.
- Hard cap remains 20 requests/minute.
- Async, if implemented, uses bounded concurrency and one global rate limiter.
- HTTP 429 stops the run immediately and reports partial results.
- The command is resumable and idempotent.
- The report includes cache hits, fetched, skipped, failed, and rate-limited
  URLs.
- Report entries include index, team, season end year, URL, cache path, status,
  and error details when applicable.
- Early-stop reports include `stopped_reason` and `stopped_at_entry`.
- The report is printed as JSON to stdout and, when `--output` is provided,
  written to that path as the same JSON.
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
