# Current Work

Status: phase_4a_in_progress

## Active Task

No task is approved, in progress, or needs review.

## Current Phase

- Phase ID: `phase-4a-legacy-scraper-consolidation`
- Phase status: `in_progress`
- Completed Phase 4A tasks:
  - `F4A-000` - Add legacy parity and acquisition smoke-test strategy.
  - `F4A-001` - Consolidate legacy scrapers behind cache-first providers.
  - `F4A-002` - Design bounded offline cached HTML processing.
- Phase 4 SQLAlchemy migration is not active; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.

## Goal

Phase 4A remains active as the legacy scraper consolidation gate. Its task set
is complete, but the phase has not been formally transitioned. The next safe
step is a Phase 4A closure or transition summary before activating any later
phase.

## Next Safe Action

Prepare a Phase 4A closure or transition summary. Ask for explicit owner
approval before activating Phase 4 SQLAlchemy migration, running live scraping,
contacting Basketball Reference, running controlled backfill, writing DB data,
applying migrations, deleting legacy/Peewee code, creating a PR, or
implementing API/frontend/OVR work.

## Latest Review Result

- `F4A-001` consolidated normal legacy Basketball Reference acquisition behind
  central cache-first providers.
- Generic Basketball Reference page acquisition now checks `HtmlCache` before
  `BasketballReferenceClient` and stores `.html.gz` on cache miss.
- Legacy player roster, totals, and advanced scrapers now share one
  team-season table adapter that reads and parses one team-season page per
  team/year, preserving loader-facing keys.
- Included legacy team scrapers now use the cache-first page provider for
  `/teams/` and `/teams/{TEAM}/{YEAR}_games.html`.
- Direct `requests.get`, direct `httpx.AsyncClient.get`, per-scraper sleeps,
  and live `asyncio.gather` fan-out were removed from consolidated legacy
  scraper paths.
- No live scraping, Basketball Reference contact, DB writes, migrations,
  controlled backfill, API/frontend/OVR, or legacy/Peewee deletion was
  introduced.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 55 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.

## Notes

No live scraping was run. No Basketball Reference contact occurred. No DB
writes, DB migrations, controlled backfill, legacy/Peewee deletion,
API/frontend/OVR, commit, push, or PR occurred.

The local branch is `feature/fase-4a-legacy-scraper-consolidation`; current
HEAD at task start was `fa5b5a7e8eb1bf1a8d7aaac005c0bc9fcdd2c8b6`.

Untracked `project.zip` existed before this task and remains outside scope.
