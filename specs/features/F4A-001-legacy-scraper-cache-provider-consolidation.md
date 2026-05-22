# F4A-001 - Legacy Scraper Cache Provider Consolidation

## Goal

Consolidate legacy Basketball Reference team-season player scrapers behind a
single cache-first HTML provider so one cached team-season page can feed roster,
totals, advanced, and other supported table parsing before any controlled raw
HTML backfill is implemented.

## Functional Requirements

- Create or document one adapter for team-season pages that normal legacy paths
  use instead of per-scraper direct HTTP access.
- The adapter must return all supported table outputs from a single HTML page
  for a team/year.
- Use `CachedTeamSeasonHtmlProvider` or an equivalent provider that delegates
  to `HtmlCache` and `BasketballReferenceClient`.
- Use `parse_team_season_page` as the new parser where compatible with required
  output shape.
- Preserve temporary compatibility with legacy `PlayerOperations` and existing
  loader-facing keys where tests depend on them.
- Avoid allowing `PlayerScraperRoster`, `PlayerScraperTotals`, and
  `PlayerScraperAdvanced` to download the same team-season page separately.
- Route included legacy team scrapers through the generic cache-first page
  provider for `/teams/` and `{YEAR}_games.html` pages.
- Keep existing legacy provider tests passing.
- Add tests proving one team/year HTML read can parse multiple supported
  tables.
- Add tests proving a cache hit does not call the client.
- Add tests proving offline paths do not require `httpx.AsyncClient`.
- Add tests proving unit tests do not use live network requests.

## Technical Requirements

- Do not use `requests.get` in new paths.
- Do not use direct `httpx.AsyncClient.get` in new paths.
- Do not add manual sleeps outside `BasketballReferenceClient`.
- Do not introduce live concurrency.
- Do not change DB schema.
- Do not add DB writes or loaders.
- Do not delete legacy or Peewee code.
- If a legacy path cannot be consolidated without unacceptable risk, document
  it as explicit debt.

## Acceptance Criteria

- `tasks/feature-list.json` remains valid JSON.
- Legacy team-season player scrapers no longer require direct
  `httpx.AsyncClient` network access for normal operation.
- Team-season roster, totals, advanced, and other supported tables can be
  parsed from one cached HTML page per team-season.
- The code avoids downloading the same `/teams/{TEAM}/{YEAR}.html` page
  separately for roster, totals, and advanced.
- Any remaining live request path goes through `BasketballReferenceClient`.
- No `requests.get` or direct `httpx.AsyncClient.get` is used for Basketball
  Reference pages in the consolidated path.
- Manual per-scraper sleeps are removed or bypassed in favor of the central
  rate-limited client.
- Existing legacy loader-compatible keys are preserved where tests depend on
  them.
- The implementation supports offline execution from `HtmlCache`.
- Included team scrapers use cache-first providers instead of direct
  `requests.get` or direct async HTTP calls.
- Unit tests use fixtures/mocks and make no network requests.
- No DB writes, Alembic migrations, API/frontend/OVR work, live scraping, or
  legacy/Peewee deletion is introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
