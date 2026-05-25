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

## Checkpoint 14 - Global Phase Governance

### What Changed

Added global phase governance, phase specs, rolling backlog metadata, and a
current-phase-aware harness init check.

### Why

Agents could block when no task was `approved` because the workflow only said to
prefer `approved` tasks or propose `pending` tasks. It did not explain how to
handle `ready` tasks, proposed phases, blocked phases, or phase transitions.

### Concepts Learned

- A rolling backlog lets the repo carry the next likely work without pretending
  everything is already approved.
- `pending` means a task exists but is not ready for execution.
- `ready` means the task is ready for owner approval in the current phase.
- `approved` means the task is selected for implementation.
- `in_progress` means one task is actively being implemented, and no other task
  should start.
- Phase governance keeps future phases designed while preventing accidental API,
  frontend, migration, or OVR implementation.

### Files to Read

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `specs/phases/phase-2-scraper-cache-integration.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

## Checkpoint 28 - Phase 4A F4A-000 Activation

### What Changed

Activated `phase-4a-legacy-scraper-consolidation` and closed `F4A-000` as the
reviewed strategy gate. Phase 4 SQLAlchemy migration remains inactive, and
`F4A-001`, `F4A-002`, `F4-001`, `F4-002`, and `F4-003` remain pending.

### Why

Legacy scraper consolidation needs an explicit validation strategy before any
refactor, controlled raw HTML backfill, loader work, or migration work starts.

### Concepts Learned

- Parser/refactor correctness should be proven offline from frozen or
  fixture-copied cached HTML.
- Legacy roster, totals, and advanced outputs remain the temporary parity
  reference until reviewed normalized contracts replace them.
- Manual live smoke tests are owner-gated, cache-first, one-page, shape-only,
  and separate from CI.
- Live concurrency stays disallowed; bounded concurrency belongs only to future
  already-cached local HTML processing.

### Files to Read

- `tasks/feature-list.json`
- `docs/roadmap/CURRENT_PHASE.md`
- `specs/phases/phase-4a-legacy-scraper-consolidation.md`
- `specs/features/F4A-000-legacy-parity-and-acquisition-smoke-test-strategy.md`
- `docs/decisions/0016-live-vs-offline-validation.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and Git Bash harness close.

### Review Questions

- Should the owner approve `F2-001` as the first Phase 2 task?

## Checkpoint 15 - Phase 2 Team-Season Fetch Cache Flow

### What Changed

Added a small team-season page helper that builds deterministic Basketball
Reference team-season URLs and fetches HTML through a cache-first flow.

### Why

Phase 2 needs one safe boundary where a `teams/{TEAM}/{YEAR}.html` page can be
obtained through `HtmlCache` and `BasketballReferenceClient` without rewriting
the legacy scraper.

### Concepts Learned

- Team-season pages can share one URL builder before parser and legacy adapter
  work.
- The cache coordination can be tested with a fake client and local fixture HTML.
- `force_refresh` should be explicit so normal validation remains offline.
- A cache miss in the outer helper should not force-refresh the inner client
  unless the caller explicitly asks for it.

### Files to Read

- `src/nba_data/scraping/team_season_pages.py`
- `tests/unit/test_team_season_pages.py`
- `tasks/feature-list.json`

### How to Test

Run `uv run pytest tests/unit/test_team_season_pages.py`, then run `uv run ruff
check .`, `uv run pytest`, and Git Bash harness validation.

### Review Questions

- Should `F2-002` route this cached HTML directly into
  `parse_team_season_page` next?

## Checkpoint 16 - Phase 2 Cached Parser Flow

### What Changed

Added a cached team-season parser helper that reads a team-season page from
`HtmlCache` and routes the HTML string into the existing pure parser.

### Why

Phase 2 needs a parser flow that starts from cached HTML and cannot accidentally
make network requests or write to the database.

### Concepts Learned

- Cache-backed parser flows should fail clearly on cache miss instead of
  fetching live pages.
- A single cached team-season HTML page can feed roster, totals, and advanced
  parser output.

### Files to Read

- `src/nba_data/scraping/team_season_pages.py`
- `tests/unit/test_team_season_pages.py`

### How to Test

Run `uv run pytest tests/unit/test_team_season_pages.py
tests/unit/test_team_season_parser.py`, then run `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

### Review Questions

- Should `F2-003` add more realistic local fixtures before expanding parser
  coverage in Phase 3?

## Checkpoint 17 - Phase 2 Realistic Team-Season Fixture

### What Changed

Added a compact hand-authored team-season HTML fixture that more closely
resembles Basketball Reference table structure without downloading or storing a
large raw page.

### Why

`F2-003` needs representative local HTML so parser/cache tests can exercise
commented wrapped tables and repeated table header rows while staying fully
offline.

### Concepts Learned

- A small fixture can cover the important parser structure without becoming a
  raw page dump.
- Commented wrapped `totals_stats` and `advanced` tables still flow through the
  existing pure parser.
- Repeated `tbody` header rows should be present in fixtures so parser tests
  prove they are ignored.

### Files to Read

- `tests/fixtures/html/team_season_realistic.html`
- `tests/unit/test_team_season_parser.py`
- `tests/unit/test_team_season_pages.py`

### How to Test

Run `uv run pytest tests/unit/test_team_season_pages.py
tests/unit/test_team_season_parser.py`, then run `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

### Review Questions

- Should `F2-003` be closed as done after review, leaving F2-004/F2-005/F2-006
  for explicit owner approval?

## Checkpoint 18 - Phase 2 Legacy Team-Season Cache Adapter

### What Changed

Added a cached team-season HTML provider and wired it into the legacy roster,
totals, and advanced team-season page scrapers as an optional path.

### Why

`F2-004` needs the legacy team-season scraper boundary to use the central
client/cache path without rewriting the whole legacy workflow or changing the
loader-facing row keys.

### Concepts Learned

- The central cache/client path can be injected into legacy scrapers without
  removing the existing async `httpx` fallback.
- The legacy parser path must keep label-based keys such as `Player`, `G`,
  `PTS`, and `PER`; the pure parser's `data-stat` keys are intentionally kept
  separate for now.
- Offline tests can prove cache-first behavior and legacy output compatibility
  with fake providers and local fixture HTML.

### Files to Read

- `src/nba_data/scraping/team_season_pages.py`
- `scrap/scrap_player/scrap_player_roster.py`
- `scrap/scrap_player/scrap_player_totals.py`
- `scrap/scrap_player/scrap_player_advanced.py`
- `tests/unit/test_legacy_team_season_scrapers.py`

### How to Test

Run `uv run pytest tests/unit/test_team_season_pages.py
tests/unit/test_legacy_team_season_scrapers.py`, then run `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

### Review Questions

- Should `F2-004` be closed as done after review, leaving the gated
  `F2-LIVE-001` smoke test pending until explicit URL approval?

## Checkpoint 19 - Phase 2 One-Page Live Smoke Test

### What Changed

Ran the gated `F2-LIVE-001` smoke test for the owner-approved URL
`https://www.basketball-reference.com/teams/BOS/2024.html` and moved the task
to `needs_review`.

### Why

The adapted legacy team-season scraper path needed one controlled real-page
check after offline tests proved the cache/client integration.

### Concepts Learned

- The central `BasketballReferenceClient` and `HtmlCache` path can fetch and
  store one Basketball Reference team-season page for downstream parser use.
- A one-request injected HTTP fuse can verify the live request count while
  still keeping the production request path inside `BasketballReferenceClient`.
- One cached team-season page can feed the pure parser and the adapted legacy
  roster, totals, and advanced scrapers.

### Result

- Cache result: miss before execution.
- Live requests: 1.
- HTTP status: 200.
- HTML chars: 928025.
- Cache path:
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`.
- Parsed tables: `['advanced', 'roster', 'totals']`.
- Legacy rows: roster 19, totals 19, advanced 19.

### How to Test

Run `uv run ruff check .`, `uv run pytest`, and Git Bash harness validation.

### Review Questions

- Should `F2-LIVE-001` be closed as done after review, leaving `F2-005` and
  `F2-006` pending for explicit owner approval?

## Checkpoint 20 - Phase 2 Cached Smoke-Test Export

### What Changed

Inspected the cached BOS 2024 team-season HTML from the `F2-LIVE-001` smoke
test and exported the parsed legacy roster, totals, and advanced outputs to
local JSON/Markdown files under `data/exports/smoke-tests/BOS-2024/`.

### Why

The live smoke test proved that the page could be fetched and cached. The
cached inspection makes the parsed result visible for review without contacting
Basketball Reference again.

### Concepts Learned

- `CachedTeamSeasonHtmlProvider` can be paired with a no-network transport fuse
  to prove a cache hit while exercising the same adapted legacy parser path.
- The cached BOS 2024 page provides roster, totals, and advanced tables with 19
  rows each.
- `data/exports` is not ignored by Git, so local export artifacts must remain
  unstaged unless the owner explicitly approves tracking them.

### Result

- Cache result: hit.
- Network requests: 0.
- Cache file size: 141649 bytes.
- HTML chars: 928025.
- Exported files: `roster.json`, `totals.json`, `advanced.json`, and
  `summary.md`.

### How to Test

Run `uv run ruff check .`, `uv run pytest`, and Git Bash harness validation.

## Checkpoint 21 - Phase 2 Live Smoke Review Closure

### What Changed

Reviewed and closed `F2-LIVE-001` as `done` after confirming the one-page live
smoke test met its acceptance criteria and passed offline validation.

### Why

The live/cache integration task needed a formal review gate before Phase 2
could move on to loader strategy planning.

### Concepts Learned

- One approved live request is enough to validate the adapted team-season
  cache/client path when offline tests and cached inspection already cover the
  parser behavior.
- The next Phase 2 step should return to non-live planning work unless the
  owner explicitly approves another gated live action.

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and Git Bash harness close.

## Checkpoint 25 - Phase 3 Parser Normalization

### What Changed

Activated and completed Phase 3. Expanded pure team-season table parsing, added
separated normalization, added offline data-quality checks, and documented the
parser/normalizer/validator boundary.

### Why

Future idempotent loaders need stable normalized rows and validation before any
database write or migration work begins.

### Concepts Learned

- A single cached team-season page can expose multiple safe player stat tables.
- `basketball_reference_player_id` should be carried from parser output through
  normalization and validation.
- Missing player IDs should be explicit debt, not inferred from `player_name`.
- `TOT` rows belong to player-season aggregate handling rather than team rows.

### Files to Read

- `src/nba_data/scraping/parsers/team_season.py`
- `src/nba_data/scraping/normalizers/team_season.py`
- `src/nba_data/validation/team_season.py`
- `docs/validation/TEAM_SEASON_PIPELINE.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and Git Bash harness close.

## Checkpoint 22 - Phase 2 Loader And Migration Planning

### What Changed

Added `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md` and
`docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`. Closed `F2-005`
and `F2-006` through `approved`, `in_progress`, `needs_review`, and `done`.

### Why

Phase 2 needed to finish with clear future boundaries for idempotent loading and
SQLAlchemy migration work without implementing loaders or applying migrations.

### Concepts Learned

- Idempotent loaders need stable natural keys and duplicate-key validation
  before writes.
- `TOT` should be modeled as a player-season aggregate, not as a real team.
- Peewee can coexist with SQLAlchemy while new DB work moves through Alembic.

### Files to Read

- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`
- `docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`
- `docs/migration/PEEWEE_TO_SQLALCHEMY.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`, and
`uv run pytest`.

## Checkpoint 23 - Phase 2 Conservative Cleanup Audit

### What Changed

Audited imports, dependencies, tracked legacy folders, docs, config, and CI.
No dependency or folder was deleted, and `uv.lock` was not edited manually.

### Why

The cleanup checkpoint needed to identify obsolete code safely without crossing
sensitive gates such as deleting legacy/Peewee code or removing dependencies.

### Concepts Learned

- Legacy folders still have active imports from tests, `scrape_main.py`, and
  legacy operations.
- `peewee`, `requests`, and `httpx` remain active dependencies.
- `tenacity` has no active imports outside lock/data, but dependency cleanup is
  better handled as a separate approved dependency task.

### Files to Read

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `progress/review.md`

### How to Test

Run `uv run ruff check .`, `uv run pytest`, and Git Bash harness validation.

## Checkpoint 24 - Phase 2 Closure

### What Changed

Marked `phase-2-scraper-cache-integration` as `done`, marked all Phase 2 tasks
as `done`, and kept Phase 3 tasks `pending`.

### Why

The scraper/cache integration phase met its done criteria and the remaining
planning tasks are reviewed. Phase 3 should start only after an explicit owner
phase transition.

### Concepts Learned

- Closing a phase is separate from activating the next one.
- A done current phase can remain the current source of truth until the owner
  approves a transition.

### Files to Read

- `docs/roadmap/CURRENT_PHASE.md`
- `specs/phases/phase-2-scraper-cache-integration.md`
- `tasks/feature-list.json`
- `progress/current.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and Git Bash harness close.

## Checkpoint 26 - Phase 4A Backlog Gate

### What Changed

Added proposed Phase 4A backlog and specs for legacy scraper consolidation
before any controlled raw HTML backfill or Phase 4 SQLAlchemy migration work.
Added ADR 0015 for live-vs-offline concurrency.

### Why

The future backfill should reuse one clean path:
`manifest -> BasketballReferenceClient -> HtmlCache -> cached HTML -> parsers`.
It should not inherit legacy direct network calls, per-scraper sleeps, or
duplicate downloads of the same team-season page for roster, totals, and
advanced tables.

### Concepts Learned

- Legacy consolidation is a separate gate from live backfill and DB loading.
- Live Basketball Reference acquisition remains sequential and cache-first.
- Offline cached HTML processing may use bounded parallelism later without
  increasing live request pressure.

### Files to Read

- `tasks/feature-list.json`
- `specs/phases/phase-4a-legacy-scraper-consolidation.md`
- `specs/features/F4A-001-legacy-scraper-cache-provider-consolidation.md`
- `docs/decisions/0015-live-vs-offline-concurrency.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

## Checkpoint 27 - Phase 4A Legacy Parity Gate

### What Changed

Added `F4A-000` as a pending Phase 4A task before `F4A-001`, created its
feature spec, and added ADR 0016 for live-vs-offline validation. `F4A-001` now
depends on `F4A-000`.

### Why

Legacy scraper consolidation needs a clear validation gate before refactoring
or controlled raw HTML backfill. Parser/refactor correctness should be proven
offline from frozen or cached HTML fixtures, while the manual live smoke test
should validate only acquisition, cache, and parser shape for one approved
team-season page.

### Concepts Learned

- Legacy output can be used as a temporary behavioral reference for DB
  compatibility.
- Live scraping is not needed for parser/refactor correctness.
- A live smoke test should be cache-first, at most one approved page, and
  shape-only.
- Concurrent work belongs only after HTML already exists locally.

### Files to Read

- `tasks/feature-list.json`
- `specs/features/F4A-000-legacy-parity-and-acquisition-smoke-test-strategy.md`
- `docs/decisions/0016-live-vs-offline-validation.md`
- `docs/decisions/0004-rate-limited-scraping.md`
- `docs/roadmap/NEXT_DECISIONS.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

## Checkpoint 28 - Phase 4A Offline Processing Spec

### What Changed

Created `specs/features/F4A-002-bounded-offline-cached-html-processing.md` and
closed `F4A-002` as a design-only documentation task.

### Why

`tasks/feature-list.json` already contained `F4A-002`, but the matching feature
spec was missing. The new spec makes the future offline processor boundary
explicit before any controlled raw HTML backfill, runtime processor, or Phase 4
loader work begins.

### Concepts Learned

- Offline cached HTML processing should start from already-cached `.html.gz`
  files and fail on cache miss.
- Future offline processors must not accept network clients or refresh cache.
- Bounded parallelism belongs only to local cached HTML work, not live
  acquisition.
- Validation remains the gate before any future idempotent loader writes.

### Files to Read

- `tasks/feature-list.json`
- `specs/features/F4A-002-bounded-offline-cached-html-processing.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `progress/current.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and Git Bash harness close.

## Checkpoint 29 - Phase 4A Legacy Scraper Consolidation

### What Changed

Implemented `F4A-001` by consolidating legacy player/team-season scrapers and
included team scrapers behind cache-first Basketball Reference providers.

### Why

Future controlled raw HTML backfill needs one responsible acquisition boundary:
cache before network, central rate-limited client on cache miss, and one
team-season page feeding multiple parsers. The legacy prototype still had
direct HTTP calls, manual sleeps, and async fan-out that could duplicate page
downloads.

### Concepts Learned

- A generic page provider can serve both team-season pages and other
  Basketball Reference pages while still using `HtmlCache`.
- A shared adapter lets legacy roster, totals, and advanced scrapers preserve
  loader-facing keys without fetching the same HTML three times.
- Included team scrapers can use the same cache-first boundary even when their
  URLs are not team-season stats pages.
- Phase 4A can close the acquisition boundary without DB writes, migrations, or
  controlled backfill execution.

### Files to Read

- `src/nba_data/scraping/team_season_pages.py`
- `scrap/scrap_player/team_season_adapter.py`
- `tests/unit/test_legacy_team_season_scrapers.py`
- `tests/unit/test_legacy_team_scrapers.py`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and Git Bash harness close.

## Checkpoint 30 - Phase 4B/4C Roadmap Transition

### What Changed

Closed the Phase 4A planning handoff and introduced Phase 4B and Phase 4C as
separate roadmap phases. Phase 4B covers controlled raw HTML acquisition into
`HtmlCache`; Phase 4C covers offline cached HTML processing and later DB load
from validated normalized rows.

`tasks/feature-list.json` now has
`current_phase_id = phase-4b-controlled-raw-html-backfill` and
`current_phase_status = proposed`. `F4B-001` is `ready`; no task is approved or
in progress.

### Why

The project needed an explicit gap between legacy scraper consolidation and
SQLAlchemy/API work: first acquire approved raw HTML safely, then migrate/load
DB structures, then process cached HTML offline into validated loader inputs.

### Concepts Learned

- Controlled backfill is acquisition only:
  `approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`.
- Offline DB loading must not load directly from raw HTML. It first parses,
  normalizes, and validates cached HTML.
- Live acquisition remains sequential and cache-first; local concurrency belongs
  only to already-cached offline work.
- Current player rows come from team-season pages. Dedicated player-page
  acquisition and parsing remains future scope.

### Files to Read

- `tasks/feature-list.json`
- `specs/phases/phase-4b-controlled-raw-html-backfill.md`
- `specs/phases/phase-4c-offline-cached-html-processing-and-load.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `docs/validation/TEAM_SEASON_PIPELINE.md`
- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

## Checkpoint 31 - Phase 4B Manifest Design

### What Changed

Closed `F4B-001` as a design-only task and added the controlled raw HTML
backfill manifest spec.

The documented acquisition path is:

```text
approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz
```

### Why

Phase 4B needs exact owner approval and auditable scope before any future live
request. The manifest design separates approval, dry-run validation, live
acquisition, and later offline processing/loading.

### Concepts Learned

- A manifest is an approved acquisition plan, not a general crawler.
- The first pilot defaults to at most five explicit `team_season` URLs.
- Live acquisition stays sequential, cache-first, 10 requests/minute by
  default, and never above 20 requests/minute.
- Player-specific pages remain future scope until a later task and exact
  manifest approve them.
- Raw HTML acquisition stays separate from DB writes, migrations, parsing/load
  execution, API/frontend work, and generated metrics.

### Files to Read

- `specs/features/F4B-001-controlled-raw-html-backfill-manifest.md`
- `tasks/feature-list.json`
- `docs/roadmap/CURRENT_PHASE.md`
- `progress/current.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

## Checkpoint 32 - Phase 4B Manifest Dry-Run Validation

### What Changed

Added `F4B-002` offline manifest validation and dry-run reporting. The dry-run
checks approved `team_season` manifests, reports expected `HtmlCache` paths,
cache hit/miss state, and estimated live request count, and exposes the flow
through `nba-data backfill dry-run <manifest.json>`.

### Why

Phase 4B needs an auditable no-network planning gate before any runtime
acquisition runner or live pilot can exist.

### Concepts Learned

- A manifest dry-run can prove scope, approval, cache paths, and request
  estimates without accepting a client or contacting Basketball Reference.
- The first pilot remains limited to explicit `team_season` URLs and at most
  five entries.
- Cache misses are only counted as estimated future live requests; they are
  not fetched during dry-run validation.

### Files to Read

- `src/nba_data/scraping/backfill_manifest.py`
- `src/nba_data/cli/main.py`
- `tests/unit/test_backfill_manifest.py`
- `tests/fixtures/manifests/approved_team_season_manifest.json`

### How to Test

Run `uv run pytest tests/unit/test_backfill_manifest.py`, then run
`python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

## Checkpoint 33 - Phase 4B Acquisition Runner

### What Changed

Added the controlled acquisition runner for approved raw HTML backfill
manifests and exposed it through
`nba-data backfill acquire <manifest.json> --execute-approved-manifest`.

### Why

Phase 4B needs a reviewed runtime path that can later execute an exact
owner-approved manifest without bypassing cache checks, rate limits, or the
central Basketball Reference client.

### Concepts Learned

- The runner should check `HtmlCache` before every client call.
- Cache hits are recorded and make no live request.
- Cache misses are fetched sequentially through a
  `BasketballReferenceClient`-compatible client and written through
  `HtmlCache`.
- Client failures should stop the run with a partial report so a future pilot
  is auditable.
- The CLI needs an explicit execution flag separate from manifest approval to
  reduce accidental live acquisition risk.

### Files to Read

- `src/nba_data/scraping/backfill_manifest.py`
- `src/nba_data/cli/main.py`
- `tests/unit/test_backfill_manifest.py`

### How to Test

Run `uv run pytest tests/unit/test_backfill_manifest.py`, then run
`python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.

## Checkpoint 34 - Phase 4B F4B-003 Review Closure

### What Changed

Closed `F4B-003` as `done` after owner approval and review. Moved
`F4B-LIVE-001` to `ready` for exact-manifest preparation while keeping Phase 4B
in `proposed` status.

### Why

The acquisition runner is implemented and validated, but the live pilot remains
a separate sensitive gate that requires owner approval for the exact manifest
before any Basketball Reference request.

### Concepts Learned

- `ready` is not approval to run live acquisition.
- The execution flag protects the CLI, but the exact manifest still needs
  owner approval before a live pilot.
- Phase 4B remains acquisition-only; parsing, loading, DB writes, migrations,
  API/frontend, and OVR work stay out of scope.

### Files to Read

- `tasks/feature-list.json`
- `docs/roadmap/CURRENT_PHASE.md`
- `progress/current.md`
- `progress/review.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and Git Bash harness close.

## Checkpoint 35 - Phase 4B Live Raw HTML Pilot

### What Changed

Ran the owner-approved `F4B-LIVE-001` two-URL raw HTML acquisition pilot using
the controlled manifest at
`tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`.

### Why

Phase 4B needed one small live proof that the approved manifest flow remains
cache-first, sequential, and limited to `.html.gz` raw HTML acquisition before
any parser/load or database work.

### Concepts Learned

- The dry-run gate correctly reported BOS 2024 as a cache hit and DEN 2023 as
  the only cache miss.
- The acquisition runner made one live request for the DEN 2023 cache miss,
  skipped the cached BOS 2024 page, and stored the fetched page through
  `HtmlCache`.
- A post-run dry-run can verify the cache now covers every manifest entry
  without contacting Basketball Reference.

### Result

- Pre-run dry-run: 2 total entries, 1 cache hit, 1 cache miss, 1 estimated live
  request.
- Acquisition: 2 processed entries, 1 cache hit, 1 fetched page, 0 failures, 1
  live request.
- New cache artifact:
  `data\raw\html\basketball-reference\teams-den-2023.html-4bfff60cb079ffe5.html.gz`.
- Post-run dry-run: 2 cache hits, 0 cache misses, 0 estimated live requests.
- Validation passed: manifest JSON, task JSON, Ruff, Pytest, and Git Bash
  harness validation.
- `F4B-LIVE-001` is now `needs_review`.

### Files to Read

- `tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`
- `tasks/feature-list.json`
- `progress/current.md`
- `progress/history.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and Git Bash harness validation.
