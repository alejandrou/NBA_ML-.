# Current Work

Status: phase_2_f2_004_needs_review

## Active Task

No task is approved or in progress.

## Current Phase

- Phase ID: `phase-2-scraper-cache-integration`
- Phase status: `in_progress`
- Last completed task: `F2-003` - Add realistic HTML fixtures without live
  scraping in tests
- Awaiting review: `F2-004` - Adapt legacy team-season scraper entrypoint to
  use client/cache.

## Goal

Review `F2-004`, then either close it as `done` or request changes. Keep all
validation offline and do not start the gated live smoke task.

## Next Safe Action

Review the F2-004 diff, verify acceptance criteria, rerun offline validation if
needed, and either mark `F2-004` as `done` or request changes. Do not start
`F2-LIVE-001` or any later task without explicit owner approval.

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
- `.\.local\start-dev.ps1`: passed; Ruff passed, Pytest 23 passed,
  PostgreSQL local ready, Alembic current revision at head.

## Notes

Working branch: `feature/fase-1-foundations`.

Phase 1 is reviewed and closed. Phase 2 is in progress. `F2-001`, `F2-002`, and
`F2-003` are reviewed and done.

`F2-004` is awaiting review. `F2-LIVE-001`, `F2-005`, and `F2-006` are pending.
No live request is part of `F2-004`.

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
database migration was applied, and no API/frontend/OVR work was implemented.

The branch still has uncommitted Phase 2 implementation/progress changes. No
commit or push has been performed yet in this handoff. After commit/push, use
the next conversation to review and close `F2-004`; do not start `F2-LIVE-001`
without explicit owner approval for the exact live URL.
