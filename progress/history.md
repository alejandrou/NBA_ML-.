# Progress History

Completed checkpoints and tasks will be recorded here.

## Checkpoint 0 - Repository Inspection

- Branch before implementation: `data_process`.
- Implementation branch: `feature/fase-1-foundations`.
- Legacy entrypoint found: `scrape_main.py`.
- README command mismatch found: documented `main.py`.
- Hardcoded legacy DB credentials found in `db_manager/db_conf.py`.
- Direct network calls found in legacy scraper modules.

## Phase 1 Implementation

- Added `AGENTS.md`, project rules, workflow, review protocol, skills, and roles.
- Added structured task list, feature specs, progress memory, roadmap docs, and ADRs.
- Added `pyproject.toml`, `uv.lock`, `.env.example`, Docker Compose, and README.
- Added `src/nba_data/` foundation for settings, cache, rate-limited client, parser, DB, and CLI.
- Added Alembic foundation and Peewee migration documentation.
- Added unit tests, fixture HTML, CI workflow, Codex review prompt, and harness scripts.
- Ran `uv sync --all-groups`.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 13 passed.
- Ran `docker compose config`: passed.
- Ran `uv run alembic history`: passed.
- Ran `uv run nba-data info`: passed.
- Ran `uv run nba-data cache path https://www.basketball-reference.com/teams/BOS/2024.html`: passed without network.
- Ran SQLAlchemy model import smoke test: passed.
- Ran harness scripts through Git Bash: init, validate, and close passed.
- Did not run live scraping or contact Basketball Reference.

## Phase 1 Review Closure

- Resolved the Git tracking blocker caused by broad `.gitignore` patterns.
- Made Phase 1 docs, specs, tasks, progress memory, harness scripts, and Codex
  prompts trackable.
- Strengthened harness init to fail when required files are ignored or
  untracked.
- Marked F1-001 through F1-011 as `done`.
- Ran `.\.local\start-dev.ps1`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 13 passed.
- Ran Git Bash harness init and validate: passed.
- Did not run live scraping or contact Basketball Reference.

## Global Phase Governance

- Added global phase governance for rolling backlog selection across all
  phases.
- Created phase specs for Phase 1 through Phase 7.
- Set `phase-2-scraper-cache-integration` as the current phase with status
  `proposed`.
- Added task metadata for current phase, phase status, valid statuses, and
  maximum approved/in-progress task counts.
- Added F2-F7 backlog tasks while keeping future phase tasks `pending`.
- Left all Phase 2 tasks unapproved; `F2-001` is the first approvable task.
- Did not run live scraping, contact Basketball Reference, migrate the database,
  or implement API/frontend/OVR work.

## Phase 2 F2-001 Implementation

- Owner approved implementing `F2-001` from the proposed Phase 2 backlog.
- Set Phase 2 to `in_progress` and moved `F2-001` to `needs_review`.
- Added a deterministic team-season URL helper for
  `teams/{TEAM}/{YEAR}.html`.
- Added a cache-first team-season HTML fetch helper that checks `HtmlCache`
  before using `BasketballReferenceClient`.
- Refined the helper so normal cache misses preserve `force_refresh=False`
  when delegating to `BasketballReferenceClient`.
- Added unit tests with fakes and local fixtures only.
- Ran `.\.local\start-dev.ps1`: passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 18 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.
- Did not run live scraping, contact Basketball Reference, migrate the database,
  or implement API/frontend/OVR work.

## Phase 2 F2-001 Review Closure

- Owner reviewed the F2-001 changes and approved closing the first Phase 2
  task.
- Marked `F2-001` as `done`.
- Kept `F2-002` and `F2-003` as `ready`; no next task was approved.
- No live scraping was run, no request to Basketball Reference was made, no
  database migration was applied, and no API/frontend/OVR work was implemented.

## Phase 2 F2-002 Implementation

- Owner approved implementing `F2-002` from the Phase 2 backlog.
- Added a cached team-season parser flow that reads HTML from `HtmlCache` and
  passes the HTML string into the pure parser.
- Cache misses raise `FileNotFoundError` and do not fall back to network.
- Added fixture-based unit tests for cached parser output, cache misses, and
  the no-client parser-flow boundary.
- Ran `uv run pytest tests/unit/test_team_season_pages.py tests/unit/test_team_season_parser.py`:
  10 passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 21 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Moved `F2-002` to `needs_review`.
- Did not run live scraping, contact Basketball Reference, migrate the
  database, or implement API/frontend/OVR work.

## Phase 2 F2-002 Handoff

- Current task state: `F2-002` is `needs_review`.
- Current phase state: `phase-2-scraper-cache-integration` remains
  `in_progress`.
- Next safe action: review the F2-002 diff and either close the task as `done`
  after approval or request changes.
- `F2-003` remains `ready` but is not approved for implementation yet.
- Continue using Git Bash at `C:\Program Files\Git\bin\bash.exe` for harness
  scripts on this Windows environment.

## Phase 2 F2-002 Review Closure

- Reviewed the cached parser flow and approved `F2-002`.
- Marked `F2-002` as `done`.
- Owner approved starting `F2-003`; moved `F2-003` into active work.
- No live scraping was run, no request to Basketball Reference was made, no
  database migration was applied, and no API/frontend/OVR work was implemented.

## Phase 2 F2-003 Implementation

- Owner approved implementing `F2-003`.
- Added a compact hand-authored team-season fixture that mimics the relevant
  Basketball Reference table structure without using a raw downloaded page.
- Covered visible roster parsing, commented wrapped totals and advanced tables,
  multiple player rows, and repeated `tbody` header rows.
- Added parser and cached-flow tests using only local fixture HTML.
- Ran `uv run pytest tests/unit/test_team_season_pages.py tests/unit/test_team_season_parser.py`:
  12 passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 23 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Moved `F2-003` to `needs_review`.
- Did not run live scraping, contact Basketball Reference, migrate the
  database, or implement API/frontend/OVR work.

## Phase 2 F2-003 Handoff

- Current task state: `F2-003` is `needs_review`.
- Current phase state: `phase-2-scraper-cache-integration` remains
  `in_progress`.
- `F2-001` and `F2-002` are reviewed and marked `done`.
- Next safe action: review the F2-003 diff and either close the task as `done`
  after validation or request changes.
- Do not start `F2-004`, run live scraping, contact Basketball Reference,
  migrate the database, remove Peewee/legacy code, or implement API/frontend/OVR
  work without explicit owner approval.
- Continue using Git Bash at `C:\Program Files\Git\bin\bash.exe` for harness
  scripts on this Windows environment.

## Phase 2 F2-003 Review Closure

- Reviewed and approved `F2-003`.
- Verified `tests/fixtures/html/team_season_realistic.html` is a compact local
  hand-authored fixture rather than a raw downloaded page dump.
- Verified the fixture covers a visible roster table, commented wrapped
  `totals_stats` and `advanced` tables, multiple player rows, and repeated
  `tbody` header rows with `class="thead"`.
- Verified tests cover both the pure parser and cached offline flow.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 23 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Marked `F2-003` as `done`.
- Did not start `F2-004`, run live scraping, contact Basketball Reference,
  migrate the database, remove Peewee/legacy code, or implement API/frontend/OVR
  work.

## Phase 2 Backlog Update - F2-LIVE-001

- Added `F2-LIVE-001` as a pending gated live smoke-test task immediately after
  `F2-004`.
- Recorded the dependency on `F2-004` and the sensitive gates for live scraping
  and contacting Basketball Reference.
- Kept `F2-004`, `F2-LIVE-001`, `F2-005`, and `F2-006` as `pending`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 23 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Did not approve or start the task, make a live request, contact Basketball
  Reference, migrate the database, or implement API/frontend/OVR work.

## Phase 2 F2-004 Implementation

- Owner approved implementing `F2-004`.
- Added a cached team-season HTML provider backed by `HtmlCache`,
  `BasketballReferenceClient`, and the existing cache-first team-season fetch
  helper.
- Wired the provider into the legacy roster, totals, and advanced team-season
  page scrapers as an optional path while preserving the old async `httpx`
  fallback.
- Preserved legacy parser output keys such as `Player`, `G`, `PTS`, and `PER`
  for existing loaders.
- Passed the optional provider through `PlayerOperations` without changing DB
  write methods.
- Added offline tests with fake providers/clients and local fixture HTML only.
- Ran `uv run pytest tests/unit/test_team_season_pages.py tests/unit/test_legacy_team_season_scrapers.py`:
  15 passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Moved `F2-004` to `needs_review`.
- Did not start `F2-LIVE-001`, run live scraping, contact Basketball Reference,
  write DB data, remove Peewee/legacy code, or implement API/frontend/OVR work.

## Phase 2 F2-004 Commit/Push Handoff

- Prepared the `F2-004` implementation and backlog/progress updates for commit
  and push on `feature/fase-1-foundations`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Next safe action after push: review `F2-004` and either mark it `done` or
  request changes.
- `F2-LIVE-001` remains pending and must not run without explicit owner
  approval for the exact live URL.
- Committed and pushed the `F2-004` implementation to
  `origin/feature/fase-1-foundations`.

## Phase 2 F2-004 Review Closure

- Reviewed and approved `F2-004`.
- Verified the cached team-season provider delegates to the central
  `HtmlCache` and `BasketballReferenceClient` path.
- Verified the legacy roster, totals, and advanced scrapers accept the injected
  provider while preserving loader-facing keys such as `Player`, `G`, `PTS`,
  and `PER`.
- Verified tests use local fixtures, fakes, and mocked HTTP only.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Marked `F2-004` as `done`.
- Kept `F2-LIVE-001`, `F2-005`, and `F2-006` pending.
- Did not start `F2-LIVE-001`, run live scraping, contact Basketball Reference,
  write DB data, migrate the database, remove Peewee/legacy code, or implement
  API/frontend/OVR work.
