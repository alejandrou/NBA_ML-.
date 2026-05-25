# Phase 4C - Offline Cached HTML Processing and Load

Status: proposed
Phase ID: `phase-4c-offline-cached-html-processing-and-load`

## Goal

Implement the offline path that consumes already-cached Basketball Reference
HTML, validates normalized data, and then loads only validated rows through
idempotent SQLAlchemy loaders.

The required flow is:

`.html.gz -> parse -> normalize -> validate -> idempotent loader -> database`

Phase 4C is not direct loading from raw HTML. Database writes happen only after
offline parsing, normalization, and validation pass.

## Preconditions

- Phase 4B has produced or verified approved cached `.html.gz` inputs.
- Phase 4 SQLAlchemy migrations and idempotent loader repositories are complete
  enough for the selected pilot data.
- `F4-002` and `F4-003` are done before any Phase 4C database load task runs.

## Phase Tasks

- `F4C-001`: Implement offline cached HTML processor.
- `F4C-002`: Connect offline processor to idempotent loaders.
- `F4C-003`: Add offline load reporting and quarantine workflow.

## Allowed Work

- Read existing `.html.gz` files through `HtmlCache` or explicit paths under
  the configured cache root.
- Fail on cache misses instead of refreshing the cache.
- Parse cached HTML with pure parser functions.
- Normalize parser output before validation.
- Validate normalized rows before any database write.
- Load validated rows through idempotent SQLAlchemy repositories.
- Use bounded local concurrency only for already-cached local work.
- Add reports for parsed, validated, loaded, skipped, and quarantined rows.

## Disallowed Work

- Live scraping or Basketball Reference contact.
- Accepting `BasketballReferenceClient`, `requests`, `httpx`, or a generic
  network client in the offline processor.
- Refreshing cache misses.
- Direct DB loading from raw HTML without parse/normalize/validate.
- Full historical loading before a pilot is proven.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.
- Deleting raw HTML, database rows, legacy code, or Peewee code without
  explicit owner approval.

## Execution Rules

- Default execution is sequential with `max_workers=1`.
- Thread workers may be used for bounded local gzip I/O if profiling or dry-run
  output shows I/O wait.
- Process workers may be used only for CPU-heavy offline parsing or validation
  after profiling shows CPU is the bottleneck.
- Async may be used only as local orchestration over already-cached inputs and
  must never schedule live acquisition.
- Partial failures must be auditable and retry-safe.

## Done Criteria

- Offline processing can run without a network client.
- Cache misses are actionable errors.
- Validated normalized rows are the only input to DB loaders.
- Idempotent upserts can be rerun without duplicates.
- Reports distinguish successful loads from validation failures and quarantined
  rows.
- No live scraping, cache refresh, API/frontend/OVR work, or full historical
  load occurred.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
