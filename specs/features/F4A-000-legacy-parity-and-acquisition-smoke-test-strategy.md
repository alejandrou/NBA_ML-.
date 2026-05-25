# F4A-000 - Legacy Parity and Acquisition Smoke-Test Strategy

## Purpose

Define the validation strategy that must exist before legacy scraper
consolidation and any controlled raw HTML backfill.

Legacy scraper output is the temporary behavioral reference for future database
compatibility. The refactor should preserve the loader-facing roster, totals,
and advanced outputs that the future DB path will depend on until those
contracts are replaced by reviewed normalized models.

Live scraping is not needed to test parser or refactor correctness. Parser
correctness must be validated from frozen or cached HTML fixtures so unit tests
and CI remain offline, deterministic, and safe.

## Offline Parity Strategy

Input is one frozen team-season HTML fixture. Prefer the existing compact
fixture `tests/fixtures/html/team_season_realistic.html` unless a future task
copies a small approved cached HTML sample into test fixtures.

The legacy path compares outputs from:

- `PlayerScraperRoster`
- `PlayerScraperTotals`
- `PlayerScraperAdvanced`

The new path compares against the consolidated cached team-season
parser/adapter introduced by the legacy scraper consolidation task.

Expected behavior:

- One HTML input can produce roster, totals, advanced, and future supported
  tables.
- The same team-season page is not downloaded separately for roster, totals,
  and advanced.
- Parser and parity tests make no network requests.
- Parser and parity tests perform no DB writes.
- Small golden JSON fixtures may store expected outputs when they make
  behavior easier to review.

The parity comparison should focus on fields needed for future DB
compatibility and existing legacy loader compatibility, not on unrelated
formatting churn.

## Manual Live Acquisition Smoke Strategy

The manual smoke test is separate from unit tests and CI. The owner must approve
the exact Basketball Reference team-season URL, team, and year before
execution.

Defaults:

- `max_live_requests = 1`
- `requests_per_minute = 10`
- Absolute maximum `requests_per_minute = 20`

The smoke test must use `BasketballReferenceClient` and `HtmlCache`.

Execution rules:

- Check `HtmlCache` first.
- If the cache hits, make no live request.
- If the cache misses and execution is approved, download the page once through
  `BasketballReferenceClient`.
- Save the result as `.html.gz` through `HtmlCache`.
- Parse the cached result and validate table presence and row/column shape.
- Do not assert exact long-term statistical equality from the live page.
- Do not write to the database.

HTTP 429 must stop the smoke test safely through the central client behavior.

## Async/Concurrency Policy

No concurrent live scraping is allowed.

Live acquisition is sequential, cache-first, and rate-limited. Async fan-out is
not allowed for Basketball Reference live requests.

Concurrent processing is allowed only after HTML exists locally. Future offline
processing may use bounded workers for parse, normalize, and validate steps
against already-cached local HTML.

Future DB loading should use idempotent batch loaders and bounded transactions,
not unbounded per-row writes.

## Validation Commands

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `bash scripts/harness/validate.sh`

On Windows, use `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
if the default `bash` command points to unavailable WSL.

## Out Of Scope

- Implementing controlled backfill.
- Running live scraping.
- Full historical scraping.
- DB loading.
- SQLAlchemy migrations.
- API, frontend, or OVR work.
- Proxy rotation, user-agent randomization, CAPTCHA bypass, or rate-limit
  evasion.
