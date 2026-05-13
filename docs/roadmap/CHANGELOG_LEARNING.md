# Learning Changelog

## Checkpoint 0 - Repository Inspection

### What Changed

No files changed during inspection.

### Why

The repository was inspected before implementation to understand the prototype.

### Concepts Learned

- The current entrypoint is `scrape_main.py`.
- The legacy code uses Peewee.
- Requests are currently spread across several scraper classes.

### Files to Read

- `scrape_main.py`
- `scrap/`
- `models/`
- `db_manager/`

### How to Test

No test command for inspection.

### Review Questions

- Which legacy scraper should be adapted first in Phase 2?

## Checkpoint 1 - Harness Documentation

### What Changed

Added project rules, workflow, review protocol, architecture, domain, roadmap,
and progress memory.

### Why

The repository needs versioned project memory so future work is repeatable.

### Concepts Learned

- Harness engineering makes the repository the source of truth.
- Workflows, skills, and progress files reduce chat-only context.

### Files to Read

- `AGENTS.md`
- `docs/ai/WORKFLOW_PROTOCOL.md`
- `docs/roadmap/CURRENT_PHASE.md`

### How to Test

Run `bash scripts/harness/init.sh` after scripts are added.

### Review Questions

- Are the project rules strict enough before adapting scrapers?

## Checkpoint 2 - Agent Roles and Progress Memory

### What Changed

Added repo-scoped skills, agent roles, workflow protocol, review protocol, and
progress files.

### Why

Future agents need clear responsibilities and durable project memory.

### Concepts Learned

- Roles separate planning, implementation, review, and research.
- `progress/` records state outside the chat.

### Files to Read

- `.agents/roles/leader.md`
- `.agents/skills/scraping-pipeline/SKILL.md`
- `progress/current.md`

### How to Test

Run `bash scripts/harness/init.sh`.

### Review Questions

- Which role should own Phase 2 scraper adaptation?

## Checkpoint 3 - Feature List and Specs

### What Changed

Added `tasks/feature-list.json` and feature specs under `specs/features/`.

### Why

Tasks need acceptance criteria, expected files, validation, and explicit scope.

### Concepts Learned

- JSON task state supports automation.
- Markdown specs explain intent for humans.

### Files to Read

- `tasks/feature-list.json`
- `specs/features/F1-007-rate-limited-client.md`

### How to Test

Inspect task statuses and run `bash scripts/harness/init.sh`.

### Review Questions

- Are any Phase 2 tasks missing from the next prompt?

## Checkpoint 4 - Settings and uv

### What Changed

Added `pyproject.toml`, `uv.lock`, `.env.example`, and `Settings`.

### Why

The project needs reproducible dependencies and environment-based config.

### Concepts Learned

- Secrets belong in environment variables.
- `pydantic-settings` validates runtime configuration.

### Files to Read

- `pyproject.toml`
- `.env.example`
- `src/nba_data/config/settings.py`

### How to Test

Run `uv sync --all-groups` and `uv run pytest tests/unit/test_settings.py`.

### Review Questions

- Is the default user agent contact text ready to replace before live scraping?

## Checkpoint 5 - Docker, README, and gitignore

### What Changed

Updated Docker Compose, README, and `.gitignore`.

### Why

Local PostgreSQL should be reproducible and secrets/raw data must stay untracked.

### Concepts Learned

- Compose defaults are development conveniences, not production secrets.
- README should state implemented features separately from planned features.

### Files to Read

- `docker-compose.yml`
- `.gitignore`
- `README.md`

### How to Test

Run `docker compose config`.

### Review Questions

- Is the local database name/user/password acceptable for development?

## Checkpoint 6 - Harness Scripts

### What Changed

Added `init.sh`, `validate.sh`, and `close.sh`.

### Why

Agents and humans need repeatable checks before and after work.

### Concepts Learned

- Harness scripts encode the project workflow as executable checks.
- This Windows machine needs Git Bash because `bash` points to WSL.

### Files to Read

- `scripts/harness/init.sh`
- `scripts/harness/validate.sh`
- `scripts/harness/close.sh`

### How to Test

Run `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Review Questions

- Should PowerShell wrapper scripts be added later for Windows convenience?

## Checkpoint 7 - Rate-Limited Client

### What Changed

Added `BasketballReferenceClient` and tests with mocked HTTP.

### Why

All future live requests need one policy-enforced path.

### Concepts Learned

- Rate limiting must be centralized to be auditable.
- `Retry-After` and repeated 429s need explicit behavior.

### Files to Read

- `src/nba_data/scraping/client.py`
- `tests/unit/test_rate_limited_client.py`

### How to Test

Run `uv run pytest tests/unit/test_rate_limited_client.py`.

### Review Questions

- Should Phase 2 adapt one legacy scraper first or all team-season page fetches together?

## Checkpoint 8 - HTML Cache

### What Changed

Added `HtmlCache` that stores `.html.gz` files under `data/raw/html`.

### Why

Cache reduces duplicate requests and preserves source HTML for repeatable parsing.

### Concepts Learned

- Raw source data and parsed/loaded data are different layers.
- Stable URL keys make cache files deterministic.

### Files to Read

- `src/nba_data/scraping/cache.py`
- `tests/unit/test_html_cache.py`

### How to Test

Run `uv run pytest tests/unit/test_html_cache.py`.

### Review Questions

- Should cache metadata be loaded into `raw.raw_pages` in Phase 2 or Phase 3?

## Checkpoint 9 - Parser Pattern

### What Changed

Added a pure team-season parser and minimal fixture HTML.

### Why

Parser tests should not make network requests or touch DB.

### Concepts Learned

- Basketball Reference often hides tables in HTML comments.
- Pure parsers are easier to test than scraper classes.

### Files to Read

- `src/nba_data/scraping/parsers/team_season.py`
- `tests/fixtures/html/team_season_minimal.html`
- `tests/unit/test_team_season_parser.py`

### How to Test

Run `uv run pytest tests/unit/test_team_season_parser.py`.

### Review Questions

- Which table should get the first full parser: roster, totals, or advanced?

## Checkpoint 10 - SQLAlchemy Foundation

### What Changed

Added SQLAlchemy base/session/models, Alembic foundation, and Peewee migration doc.

### Why

New schema work needs versioned migrations and a path away from Peewee.

### Concepts Learned

- Alembic turns schema changes into reviewable files.
- Peewee can remain legacy while new code uses SQLAlchemy.

### Files to Read

- `src/nba_data/db/models/raw.py`
- `src/nba_data/db/models/core.py`
- `docs/migration/PEEWEE_TO_SQLALCHEMY.md`

### How to Test

Run `uv run pytest`. Run Alembic only with local PostgreSQL available.

### Review Questions

- Should Phase 2 create real loader repositories or only parser outputs first?

## Checkpoint 11 - CI and Review Prompt

### What Changed

Added GitHub Actions CI and Codex review prompt.

### Why

Basic checks should run consistently without scraping live.

### Concepts Learned

- CI should validate code, not run live data jobs.
- Review prompts encode repository-specific review risks.

### Files to Read

- `.github/workflows/ci.yml`
- `.github/codex/prompts/review.md`
- `docs/ci/CODEX_GITHUB_ACTION.md`

### How to Test

Run `uv run ruff check .` and `uv run pytest`.

### Review Questions

- Should future CI add DB integration tests behind a separate marker?

## Checkpoint 12 - Final Validation

### What Changed

Ran validation and updated progress memory.

### Why

Phase 1 should close with a clear validation record.

### Concepts Learned

- Automated validation and human review are separate gates.
- Environment differences, like WSL vs Git Bash, should be recorded.

### Files to Read

- `progress/history.md`
- `progress/review.md`
- `tasks/feature-list.json`

### How to Test

Run `uv run ruff check .`, `uv run pytest`, and Git Bash harness validation.

### Review Questions

- After review, should these tasks move from `needs_review` to `done`?

## Checkpoint 13 - Phase 1 Review Closure

### What Changed

Fixed the Git ignore policy, added tracking guards to the harness, and closed
F1-001 through F1-011.

### Why

Phase 1 source-of-truth files must be visible to Git, CI, reviewers, and future
agents. A file that only exists locally but is ignored cannot satisfy review
acceptance criteria.

### Concepts Learned

- `git status` can look clean while required ignored files are invisible to the
  branch.
- Harness checks should verify required files are tracked, not just present.

### Files to Read

- `.gitignore`
- `scripts/harness/init.sh`
- `progress/review.md`

### How to Test

Run `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`, `uv run ruff
check .`, and `uv run pytest`.

### Review Questions

- Which Phase 2 scraper adaptation should be approved first?
