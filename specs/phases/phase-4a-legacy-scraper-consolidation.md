# Phase 4A - Legacy Scraper Consolidation

Status: done
Phase ID: `phase-4a-legacy-scraper-consolidation`

## Goal

Prepare legacy Basketball Reference scraper paths for future controlled raw
HTML backfill by consolidating team-season page acquisition behind the central
cache-first provider.

The target pipeline is:

`one team-season URL -> HtmlCache/BasketballReferenceClient -> one raw HTML file -> multiple table parsers`

This phase must prevent the future backfill from inheriting duplicated live
downloads or direct network access from legacy player/team-season scrapers.

## Context

The new platform already has `BasketballReferenceClient`, `HtmlCache`,
`CachedTeamSeasonHtmlProvider`, `build_team_season_url`, and
`parse_team_season_page`. Phase 3 also established pure parser, normalizer, and
validator boundaries over cached team-season HTML fixtures.

`F4A-000` is the first Phase 4A gate. It defines offline parity validation and
a manual one-page live acquisition smoke-test strategy before legacy scraper
consolidation or controlled raw HTML backfill work proceeds.

`F4A-002` is the bounded offline cached HTML processing design gate. It defines
how already-cached `.html.gz` files can later be parsed, normalized, and
validated with bounded local execution before any Phase 4 idempotent loader
writes.

At phase start, legacy scrapers under `scrap/` and the legacy entrypoint in
`scrape_main.py` contained direct HTTP seams, manual sleeps, async gathering,
BeautifulSoup table parsing, and Peewee loading behavior. Phase 4A closed the
normal Basketball Reference acquisition boundary for the supported legacy
player/team-season and included team scraper paths before controlled backfill.

## Legacy Problems Addressed

- `PlayerScraperRoster`, `PlayerScraperTotals`, and
  `PlayerScraperAdvanced` previously could fetch the same
  `/teams/{TEAM}/{YEAR}.html` page separately.
- Legacy player/team-season scrapers previously retained direct
  `httpx.AsyncClient` request paths and manual per-scraper sleeps.
- Legacy team scrapers previously included direct `requests.get` or direct
  async HTTP usage for Basketball Reference pages.
- `asyncio.gather` previously could schedule many team-season scraper tasks
  even though live acquisition must be cache-first and rate-limited.
- Broader parsing/loading separation remains future migration work, but Phase
  4A introduced no DB writes and did not remove legacy/Peewee code.

Legacy anti-pattern to avoid:

`roster scraper -> live request`

`totals scraper -> live request`

`advanced scraper -> live request`

## Allowed Work During Phase

- Define the legacy-vs-new offline parity strategy from frozen or cached HTML
  fixtures.
- Document a gated one-page live acquisition smoke-test strategy that uses
  `BasketballReferenceClient` and `HtmlCache`.
- Add or wrap a single legacy-compatible adapter for team-season pages.
- Route normal legacy player/team-season HTML access through
  `CachedTeamSeasonHtmlProvider` or an equivalent cache-first provider.
- Parse roster, totals, advanced, and other supported team-season tables from
  one cached HTML page.
- Use `parse_team_season_page` where compatible with required outputs.
- Preserve temporary legacy loader-compatible row keys where tests depend on
  them.
- Add fixture/mock-based tests that make no network requests.
- Document any legacy paths that cannot be consolidated safely yet.

## Disallowed Work During Phase

- Live scraping or Basketball Reference contact.
- Controlled raw HTML backfill execution.
- Full historical scraping.
- DB loading or new DB writes.
- SQLAlchemy schema or Alembic migration changes.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.
- Deleting legacy scraper modules, Peewee models, local raw HTML, exports, or
  database files.
- Proxy rotation, user-agent randomization, CAPTCHA bypass, or rate-limit
  evasion.

## Acceptance Criteria

- `F4A-000` and `F4A-002` are complete Phase 4A design gates.
- `F4A-001` is complete as the Phase 4A implementation gate.
- `F4A-000` defines how to validate legacy-vs-new parser parity offline before
  legacy consolidation starts.
- `F4A-002` defines how future offline cached HTML processing reads only
  already-cached `.html.gz`, accepts no network client, uses bounded
  configurable execution, and delegates DB writes to later Phase 4 idempotent
  loaders.
- One team-season URL can feed one cached HTML file and multiple supported
  table parsers.
- Legacy player/team-season paths no longer require direct
  `httpx.AsyncClient` access for normal operation.
- Remaining live request paths go through `BasketballReferenceClient`.
- Unit tests use local fixtures or mocks only.
- No DB writes, migrations, API/frontend/OVR work, or legacy/Peewee deletion is
  introduced.
- Included legacy team scrapers use the central cache-first provider path for
  Basketball Reference pages instead of direct `requests.get` or direct async
  HTTP usage.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Closure State

Phase 4A is closed as a documentation and implementation gate. `F4A-000`,
`F4A-001`, and `F4A-002` are `done`; no live scraping, controlled backfill,
database writes, migrations, API/frontend/OVR work, or legacy/Peewee deletion
occurred.

## Handoff To Controlled Raw HTML Backfill

Phase 4A hands off a clean acquisition boundary to any later controlled raw
HTML backfill:

`manifest -> BasketballReferenceClient -> HtmlCache -> cached HTML -> parsers`

The future backfill should consume a manifest of approved URLs, acquire each
page once through the central client/cache path, and parse cached HTML without
reintroducing direct per-table scraper downloads.
