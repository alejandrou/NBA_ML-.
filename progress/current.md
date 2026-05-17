# Current Work

Status: phase_2_f2_004_done

## Active Task

No task is approved or in progress.

## Current Phase

- Phase ID: `phase-2-scraper-cache-integration`
- Phase status: `in_progress`
- Last completed task: `F2-004` - Adapt legacy team-season scraper entrypoint
  to use client/cache.
- No Phase 2 task is approved, in progress, or awaiting review.

## Goal

Phase 2 remains in progress with the gated live smoke task and later planning
tasks still pending. Keep all validation offline unless the owner explicitly
approves a live request.

## Next Safe Action

Ask the owner which pending Phase 2 task to approve next. Do not start
`F2-LIVE-001`, `F2-005`, `F2-006`, or any later task without explicit owner
approval.

## Files Expected

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `specs/phases/`
- `tasks/feature-list.json`
- `src/nba_data/scraping/team_season_pages.py`
- `scrap/scrap_player/scrap_player_roster.py`
- `scrap/scrap_player/scrap_player_totals.py`
- `scrap/scrap_player/scrap_player_advanced.py`
- `db_manager/player_operations/player_operations.py`
- `tests/unit/test_team_season_pages.py`
- `tests/unit/test_legacy_team_season_scrapers.py`
- `tests/unit/test_team_season_parser.py`
- `tests/fixtures/html/team_season_realistic.html`
- `docs/roadmap/TASKS.md`
- `docs/roadmap/CHANGELOG_LEARNING.md`

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Notes

Working branch: `feature/fase-1-foundations`.

Phase 1 is reviewed and closed. Phase 2 is in progress. `F2-001`, `F2-002`,
`F2-003`, and `F2-004` are reviewed and done.

`F2-LIVE-001`, `F2-005`, and `F2-006` are pending. `F2-LIVE-001` requires
explicit owner approval of the exact live URL before any request.

`F2-004` added a cached team-season HTML provider and wired it into the legacy
roster, totals, and advanced team-season page scrapers as an optional path. The
legacy output shape remains label-based for existing loaders.

`F2-002` added `parse_cached_team_season_page`, which reads team-season HTML
from `HtmlCache`, raises `FileNotFoundError` on cache miss, and routes the HTML
string into the existing pure parser. The helper does not accept a client and
does not touch the database.

`F2-003` added and closed a compact hand-authored realistic team-season fixture
with a visible roster table, commented wrapped totals and advanced tables,
multiple player rows, and repeated `thead` rows. Parser and cached-flow tests
now cover that fixture offline.

No live scraping was run, no request to Basketball Reference was made, no
database write or migration was applied, and no API/frontend/OVR work was
implemented.
