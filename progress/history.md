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
