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
