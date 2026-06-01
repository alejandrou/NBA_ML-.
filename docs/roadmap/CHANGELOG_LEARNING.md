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

## Checkpoint 36 - Phase 4B Live Pilot Review Closure

### What Changed

Reviewed and closed `F4B-LIVE-001` as `done` after confirming the owner-approved
two-URL raw HTML pilot met its acceptance criteria and passed offline
validation.

### Why

The pilot needed a formal review gate before any roadmap decision about closing
Phase 4B, starting Phase 4C, or approving Phase 4 SQLAlchemy migration work.

### Concepts Learned

- The controlled pilot produced the intended cache state: BOS 2024 stayed a
  cache hit and DEN 2023 became a readable `.html.gz` cache artifact.
- A post-run dry-run is the safest repeatable proof that the manifest now needs
  zero live requests.
- Closing the live pilot does not approve Phase 4C, SQLAlchemy migrations,
  offline loading, API/frontend work, or another live manifest.

### Files to Read

- `tasks/feature-list.json`
- `tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`
- `progress/review.md`
- `progress/current.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`,
`python -m json.tool tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`,
`uv run ruff check .`, `uv run pytest`, and Git Bash harness validation.

## Checkpoint 37 - Phase 4B Closure And Phase 4 SQLAlchemy Transition

### What Changed

Closed `phase-4b-controlled-raw-html-backfill` and moved the current phase to
`phase-4-sqlalchemy-migration` with status `proposed`. `F4-001` is now
`ready`, while `F4-002`, `F4-003`, and Phase 4C remain `pending`.

### Why

Phase 4B met its acquisition-only done criteria. The next roadmap step is to
prepare reviewable SQLAlchemy/Alembic migration work before Phase 4C can load
validated offline processing results.

### Concepts Learned

- Closing a completed acquisition phase is separate from approving migration
  implementation.
- `ready` marks the next candidate task without starting schema work.
- Phase 4C must wait for enough SQLAlchemy schema and idempotent loader support.

### Files to Read

- `docs/roadmap/CURRENT_PHASE.md`
- `tasks/feature-list.json`
- `specs/phases/phase-4-sqlalchemy-migration.md`
- `docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, `uv run alembic check`, and Git Bash harness validation.

## Checkpoint 38 - F4-001 Core SQLAlchemy Migration

### What Changed

Implemented the first additive Phase 4 core schema slice with SQLAlchemy models,
Alembic revision `0002_core_team_player_season.py`, an F4-001 feature spec, and
offline metadata tests.

### Why

Phase 4C loading needs stable core relationships before idempotent repositories
can safely connect validated normalized rows to teams, players, and seasons.

### Concepts Learned

- `TOT` belongs to future player-season aggregate handling and must not be
  inserted as a real team-season row.
- Core relationship tables can be introduced before loader implementation as
  long as the migration is additive and Peewee remains untouched.
- Alembic SQL generation can validate revision shape without PostgreSQL, but
  drift checks still require a running local database.

### Files to Read

- `specs/features/F4-001-core-team-player-season-sqlalchemy-migrations.md`
- `src/nba_data/db/models/core.py`
- `alembic/versions/0002_core_team_player_season.py`
- `tests/unit/test_core_models.py`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, `uv run alembic upgrade head`, `uv run alembic check`, and Git
Bash harness validation. Local PostgreSQL must be running for the online
Alembic commands.

## Checkpoint 39 - F4-003 Database Integration Validation

### What Changed

Closed `F4-001` as `done` and implemented `F4-003` with a dedicated local DB
validation harness. The raw timestamp metadata now matches the existing
nullable Alembic schema, so `alembic check` is clean.

### Why

Phase 4 loader work needs a repeatable migration validation path before any
idempotent repositories or database load behavior are introduced.

### Concepts Learned

- The previous Alembic drift was metadata-only: the models implied NOT NULL
  while `0001_initial_raw_core` created nullable timestamp columns.
- Aligning metadata to the existing migration avoids a risky raw-table
  constraint change and keeps validation non-destructive.
- `scripts/harness/db-validate.sh` is now the explicit local PostgreSQL check
  for migration work.

### Files to Read

- `specs/features/F4-003-database-integration-validation-path.md`
- `scripts/harness/db-validate.sh`
- `src/nba_data/db/models/raw.py`
- `tests/unit/test_raw_models.py`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`.

## Checkpoint 40 - F4-002 Idempotent Loader Repositories

### What Changed

Implemented the first Phase 4 idempotent loader slice for SQLAlchemy core
identity and membership tables.

### Why

Phase 4C needs loader repositories that can accept validated normalized rows
and rerun safely before cached HTML processing is connected to database writes.

### Concepts Learned

- Loader validation and duplicate natural-key checks must happen before any
  ORM object is created.
- Portable select-then-insert/update logic is enough for the first core loader
  slice and keeps behavior testable across SQLite and PostgreSQL.
- Loader and repository methods should flush when IDs are needed, but must not
  commit; caller-owned transactions make rollback behavior explicit.
- `TOT` aggregate rows can create player-season identity records without
  creating real team, team-season, or player-team-season rows.
- PostgreSQL smoke tests can run inside an explicit rollback transaction after
  Alembic migration validation.

### Files to Read

- `src/nba_data/db/repositories/core.py`
- `src/nba_data/scraping/loaders/team_season.py`
- `tests/unit/test_team_season_loader.py`
- `tests/integration/test_team_season_loader_postgres.py`
- `specs/features/F4-002-idempotent-loader-repositories.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`.

## Checkpoint 41 - Phase 4 Closure

### What Changed

Reviewed and closed `F4-002`, then marked
`phase-4-sqlalchemy-migration` as `done`. Phase 4C remains pending until
explicit owner approval.

### Why

Phase 4 now has the reviewed SQLAlchemy core schema, idempotent loader
repositories for validated normalized rows, and repeatable local PostgreSQL
validation needed before any future offline cached HTML processing or loading
phase begins.

### Concepts Learned

- Loader review should prove validation-before-write, idempotency, rollback
  behavior, and name preservation before closing the task.
- `TOT` aggregate handling can create player-season identity without creating
  false team membership rows.
- Closing a phase does not approve the next phase; Phase 4C still needs an
  explicit transition and task approval.

### Files to Read

- `progress/review.md`
- `progress/history.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, Git Bash harness validation, Git Bash DB validation, and
`uv run alembic current`.

## Checkpoint 42 - Phase 4C Planning Transition

### What Changed

Created `feature/phase-4c-offline-cached-html-processor`, activated
`phase-4c-offline-cached-html-processing-and-load` as the current approved
phase, moved `F4C-001` to `ready`, and added the missing F4C-001 feature spec.

### Why

Phase 4 was closed and merged, and the owner approved the roadmap transition to
Phase 4C plus preparation of `F4C-001`. The task remains unapproved so runtime
code does not start until the next explicit implementation checkpoint.

### Concepts Learned

- A phase can be approved while its first task remains only `ready`.
- `F4C-001` is processor-only: existing `.html.gz` files feed parse,
  normalize, and validate steps, with no network client and no DB writes.
- Loader connection belongs to `F4C-002`; reporting and quarantine workflow
  belongs to `F4C-003`.

### Files to Read

- `docs/roadmap/CURRENT_PHASE.md`
- `tasks/feature-list.json`
- `specs/phases/phase-4c-offline-cached-html-processing-and-load.md`
- `specs/features/F4C-001-offline-cached-html-processor.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json` and
`C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`.

## Checkpoint 43 - F4C-001 Offline Cached HTML Processor

### What Changed

Implemented the first Phase 4C runtime boundary in
`src/nba_data/scraping/offline_processor.py` and added offline unit tests in
`tests/unit/test_offline_processor.py`.

### Why

The owner approved `F4C-001`, whose scope is existing cached `.html.gz` inputs
through parse, normalize, and validate only. Loader connection remains reserved
for `F4C-002`.

### Concepts Learned

- A processor report can expose only validated rows while keeping invalid rows
  out of loader reach.
- Cache misses should be entry-level failures in offline processing, not a
  reason to refresh the cache.
- Bounded workers are safe only when the work is local cached gzip I/O and the
  final report preserves input order.

### Files to Read

- `src/nba_data/scraping/offline_processor.py`
- `tests/unit/test_offline_processor.py`
- `specs/features/F4C-001-offline-cached-html-processor.md`
- `progress/current.md`

### How to Test

Run `uv run pytest tests/unit/test_offline_processor.py`,
`python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

## Checkpoint 44 - F4C-001 Review Closure

### What Changed

Reviewed and approved `F4C-001`, then marked the task `done` while keeping
Phase 4C in progress and leaving `F4C-002` and `F4C-003` pending.

### Why

The offline cached HTML processor met the feature spec: it reads existing
`.html.gz` inputs, parses, normalizes, validates, and reports per-input
successes or failures without network clients, cache refresh, database writes,
or loader connection.

### Concepts Learned

- Review closure should update the task board, current phase notes, review
  notes, history, and learning changelog together.
- Processor-only closure keeps loader integration behind the next explicit
  task approval.
- Offline validation can pass while the PostgreSQL integration smoke test stays
  skipped when local database prerequisites are not active.

### Files to Read

- `progress/review.md`
- `progress/current.md`
- `docs/roadmap/TASKS.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

## Checkpoint 45 - F4C-002 Offline Processor Loader Connection

### What Changed

Connected validated offline processor entries to the existing idempotent core
loader through `src/nba_data/scraping/offline_loader.py` and added focused
offline tests in `tests/unit/test_offline_loader.py`.

### Why

The owner approved `F4C-002` only: validated cached HTML processor output can
now flow into Phase 4 core loaders while `F4C-003` reporting and quarantine
workflow remains pending.

### Concepts Learned

- Entry-level savepoints let one loader failure roll back partial writes without
  requiring the orchestration layer to own the outer transaction.
- Processor failures are already pre-loader failures, so the loader bridge
  should skip them rather than reclassify or quarantine them in `F4C-002`.
- Source lineage can stay useful at report level without adding schema columns.

### Files to Read

- `src/nba_data/scraping/offline_loader.py`
- `tests/unit/test_offline_loader.py`
- `specs/features/F4C-002-connect-offline-processor-to-idempotent-loaders.md`
- `progress/current.md`

### How to Test

Run `uv run pytest tests/unit/test_offline_loader.py`,
`python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

## Checkpoint 46 - F4C-002 Review Closure

### What Changed

Reviewed and approved `F4C-002`, marked it `done`, and kept Phase 4C in
progress with `F4C-003` still pending until explicit owner approval.

### Why

The loader bridge met the feature spec: it loads only validated offline
processor entries through the existing idempotent core loader, skips processor
failures, rolls back failed entries with savepoints, avoids commits, and keeps
source lineage at the returned result/report level only.

### Concepts Learned

- Review closure for loader work should prove both idempotency and transaction
  ownership boundaries.
- Savepoint tests are enough for `F4C-002`; richer reporting and quarantine
  behavior remains a separate `F4C-003` concern.
- Source lineage can support operator troubleshooting without adding schema
  columns.

### Files to Read

- `progress/review.md`
- `progress/current.md`
- `src/nba_data/scraping/offline_loader.py`
- `tests/unit/test_offline_loader.py`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

## Checkpoint 47 - F4C-003 Offline Load Reporting And Quarantine

### What Changed

Added the F4C-003 feature spec, an offline audit/quarantine report builder, and
focused unit tests. Processor validation failures now preserve quarantined rows
separately from validated rows, and loader failures preserve the validated rows
that failed to load for operator review.

### Why

Phase 4C needs an auditable retry workflow before broader offline loads. The
operator needs to see parsed, validated, loaded, skipped, and quarantined row
counts, plus source context and retry hints, without adding database schema or
contacting Basketball Reference.

### Concepts Learned

- Quarantine belongs at the report boundary for this slice; it does not require
  new DB tables or lineage columns.
- Validation-failed rows can be visible for debugging while still staying out
  of `validated_rows` and loader input.
- Loader failure quarantine should capture only the failed entry rows because
  entry-level savepoints already isolate partial writes.

### Files to Read

- `specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md`
- `src/nba_data/scraping/offline_reporting.py`
- `tests/unit/test_offline_reporting.py`
- `docs/validation/TEAM_SEASON_PIPELINE.md`

### How to Test

Run `uv run pytest tests/unit/test_offline_reporting.py`, then run
`python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed on rerun with a longer timeout, 106 passed, 1
  skipped, and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Checkpoint 48 - F4C-003 Review Closure And Phase 4C Closure

### What Changed

Reviewed and approved `F4C-003`, marked it `done`, and closed
`phase-4c-offline-cached-html-processing-and-load` as `done`.

### Why

Phase 4C now has all three reviewed pieces needed for the offline cached HTML
path: processor, loader bridge, and audit/quarantine reporting. Closing the
phase preserves the next boundary: Phase 5/API work remains pending until the
owner explicitly approves a transition.

### Concepts Learned

- Report-level quarantine is enough for this phase; persisted lineage columns
  and DB-backed quarantine tables remain future design work.
- Phase closure should not automatically activate the next phase.
- The next transition should be a proposal, not an implementation of API,
  frontend, OVR, rankings, similarity, or ML.

### Files to Read

- `progress/review.md`
- `progress/current.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`,
and `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`.

### Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 106 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Checkpoint 49 - Phase 4D Planning Transition

### What Changed

Introduced `phase-4d-full-offline-database-preparation` as the current approved
pre-API phase, added four Phase 4D tasks, and created Phase 4D phase and feature
specs.

### Why

Future API work should be developed against a real local PostgreSQL database
loaded from existing cached HTML, not against mocks. Phase 4D adds that
preparation layer while keeping live scraping, cache refresh, and API
implementation out of scope.

### Concepts Learned

- A full offline database preparation phase can sit between cached processing
  and API work without approving API implementation.
- Cache inventory should happen before any broad offline backfill so unsupported,
  duplicate, missing-metadata, and unreadable cache files are visible.
- Data quality checks should prove relationship coherence before API endpoints
  depend on the database.

### Files to Read

- `specs/phases/phase-4d-full-offline-database-preparation.md`
- `specs/features/F4D-001-cached-html-inventory.md`
- `specs/features/F4D-002-full-offline-backfill-command.md`
- `specs/features/F4D-003-data-quality-validation-checks.md`
- `specs/features/F4D-004-api-ready-database-readiness-documentation.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 106 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings after staging the new
  Phase 4D planning files required by the harness tracking guard.

### Review Questions

- Should the owner approve `F4D-001` as the first implementation task?

## Checkpoint 50 - Phase 4D-A Controlled Acquisition Planning

### What Changed

Inserted Phase 4D-A as a controlled NBA team-season cache acquisition subphase
inside Phase 4D, before cache inventory and database preparation work.

### Why

Phase 4D needs real cached Basketball Reference NBA team-season HTML before it
can inventory, process, load, and validate a useful local PostgreSQL database
for future API development.

### Concepts Learned

- Seasons 2000-2025 are Basketball Reference season end years.
- The NBA team-season manifest for this range must contain exactly 775 unique
  `/teams/{TEAM}/{YEAR}.html` URLs.
- Live acquisition needs a separate task with explicit owner approval, an
  execution flag, cache-first behavior, a global rate limiter, and immediate
  stop/report behavior on HTTP 429.

### Files to Read

- `specs/phases/phase-4d-full-offline-database-preparation.md`
- `specs/features/F4D-ACQ-001-nba-team-season-manifest.md`
- `specs/features/F4D-ACQ-LIVE-001-controlled-nba-team-season-cache-acquisition.md`
- `specs/features/F4D-ACQ-002-acquisition-report-and-cache-coverage-review.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 106 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.

### Review Questions

- Should the owner approve `F4D-ACQ-001` as the first Phase 4D-A implementation
  task?

## Checkpoint 51 - F4D-ACQ-001 NBA Team-Season Manifest Dry Run

### What Changed

Implemented deterministic NBA team-season manifest generation and dry-run
coverage reporting for Phase 4D-A. The new CLI command
`uv run nba-data acquisition dry-run-nba-team-seasons` prints the generated
dry-run report as JSON.

### Why

Phase 4D-A needs an explicit, reviewable URL set before any owner-approved live
cache acquisition can happen. The first task proves the 775-URL scope and cache
coverage without contacting Basketball Reference or writing raw HTML.

### Concepts Learned

- The 2000-2025 Basketball Reference season-end-year catalog has 775 NBA
  team-season URLs: 29 teams for 2000-2004 and 30 teams for 2005-2025.
- Manifest generation can stay deterministic in code while the future live
  acquisition task remains separately gated.
- Dry-run coverage only needs `HtmlCache.path_for_url(...).exists()`, so it can
  estimate missing cache entries without reading or writing cached HTML.

### Files to Read

- `src/nba_data/scraping/nba_team_season_manifest.py`
- `tests/unit/test_nba_team_season_manifest.py`
- `src/nba_data/cli/main.py`
- `specs/features/F4D-ACQ-001-nba-team-season-manifest.md`

### How to Test

Run `uv run pytest tests/unit/test_nba_team_season_manifest.py`,
`python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- `uv run pytest tests/unit/test_nba_team_season_manifest.py`: passed, 7
  passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 113 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 113
  passed, 1 skipped, and 6 Peewee deprecation warnings.

### Outcome

- `F4D-ACQ-001` was reviewed and approved for closure.
- `F4D-ACQ-LIVE-001` remains `pending` until separate owner approval plus its
  execution flag.

## Checkpoint 52 - F4D-ACQ-001 Review Closure

### What Changed

Reviewed and closed `F4D-ACQ-001` as `done`. Phase 4D remains `in_progress`,
and all live acquisition plus later database preparation tasks remain
`pending`.

### Why

The manifest and dry-run implementation meets the approved acquisition planning
scope, so the project can now wait for an explicit owner decision on controlled
live acquisition without starting it automatically.

### Concepts Learned

- Review closure should update the task state separately from implementation
  commits when the worktree is already clean.
- `F4D-ACQ-LIVE-001` remains a sensitive-gate task even after the manifest task
  is done.

### Files to Read

- `progress/review.md`
- `progress/history.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed on rerun with a longer timeout, 113 passed, 1
  skipped, and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 113
  passed, 1 skipped, and 6 Peewee deprecation warnings.

### Review Questions

- Should the owner approve `F4D-ACQ-LIVE-001` controlled live cache acquisition
  in a separate session with the required execution flag?

## Checkpoint 53 - Phase 4D-A Acquisition Report Handoff

### What Changed

Documented the controlled Phase 4D-A acquisition report and cache coverage
handoff in `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md`, and moved
`F4D-ACQ-002` to review state.

### Why

Phase 4D needs a recorded handoff that proves the reviewed NBA team-season
cache is complete before cache inventory and offline processing can start.

### Concepts Learned

- Acquisition review and cache-coverage review are separate from acquisition
  execution.
- A complete handoff should preserve report totals, coverage status, and prior
  aborted attempts without implying new scraping work.
- `F4D-001` should remain offline and cache-only.

### Files to Read

- `reports/acquisition-2000-2025-20260530.json`
- `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md`
- `progress/current.md`

### How to Test

Run `python -m json.tool tasks/feature-list.json` and the repository validation
commands.

### Review Questions

- Should the cache inventory task carry forward the coverage counts into its
  own report template?

## Checkpoint 53 - F4D-ACQ-LIVE-001 Offline Command Implementation

### What Changed

Implemented the controlled NBA team-season acquisition command without running
it live. The command requires both `--owner-approved` and
`--execute-approved-manifest`, verifies the deterministic 775-entry manifest
before creating the live client, skips cache hits without overwrite, validates
HTML-shaped content before storage, and reports partial stops with entry-level
details.

### Why

The project needs the live acquisition mechanism to be reviewable before any
network execution. This keeps owner approval for implementation separate from
owner approval for contacting Basketball Reference.

### Concepts Learned

- Live command approval should have two independent gates: an owner approval
  flag and an execution flag.
- Deterministic manifest validation must happen before creating the live HTTP
  client.
- Cache writes for live acquisition should use temporary verified gzip files so
  failed writes do not leave partial final `.html.gz` files.
- A useful acquisition report needs both aggregate stop details and per-entry
  context for later coverage review.

### Files to Read

- `src/nba_data/scraping/nba_team_season_acquisition.py`
- `tests/unit/test_nba_team_season_acquisition.py`
- `src/nba_data/cli/main.py`
- `specs/features/F4D-ACQ-LIVE-001-controlled-nba-team-season-cache-acquisition.md`

### How to Test

Run `uv run pytest tests/unit/test_nba_team_season_acquisition.py`,
`python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- `uv run pytest tests/unit/test_nba_team_season_acquisition.py`: passed, 12
  passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed on rerun with a longer timeout, 125 passed, 1
  skipped, and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 125
  passed, 1 skipped, and 6 Peewee deprecation warnings.

### Outcome

- `F4D-ACQ-LIVE-001` is `needs_review`.
- No live acquisition was executed for this refinement checkpoint.

## Checkpoint 54 - F4D-ACQ-LIVE-001 Flexible-Year CLI Refinement

### What Changed

Refined the live acquisition command so the owner can request a specific
inclusive season-end-year range while preserving the two safety flags. Added
optional `--output` support to write the same JSON report printed to stdout.

### Why

The full 2000-2025 acquisition can take a long time. Supporting reviewed
subsets such as 2020-2025 lets the owner download smaller chunks from the
console without bypassing the acquisition safety rules.

### Concepts Learned

- Flexible live acquisition should still validate the full reviewed manifest
  before filtering to a requested range.
- `START_YEAR END_YEAR` should be required for live commands so operator intent
  is explicit.
- Dry-run can stay as the full-manifest preview while live execution supports
  narrower reviewed ranges.
- Report output should be usable both as stdout JSON and as a saved file for
  later review.

### Files to Read

- `src/nba_data/scraping/nba_team_season_acquisition.py`
- `src/nba_data/cli/main.py`
- `tests/unit/test_nba_team_season_acquisition.py`
- `specs/features/F4D-ACQ-LIVE-001-controlled-nba-team-season-cache-acquisition.md`

### How to Test

Run `uv run pytest tests/unit/test_nba_team_season_acquisition.py
tests/unit/test_nba_team_season_manifest.py`, `python -m json.tool
tasks/feature-list.json`, `uv run ruff check .`, `uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- Focused acquisition and manifest tests: passed, 25 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 131 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 131
  passed, 1 skipped, and 6 Peewee deprecation warnings.

### Outcome

- `F4D-ACQ-LIVE-001` remains `needs_review`.
- No live acquisition was executed for the prior CLI refinement checkpoint.

## Checkpoint 55 - F4D-ACQ-LIVE-001 Full Acquisition

### What Changed

Ran the owner-approved full 2000-2025 NBA team-season acquisition through the
controlled command and produced a JSON report under `reports/`.

### Why

The Phase 4D-A cache needs complete Basketball Reference NBA team-season HTML
coverage before the next acquisition-review and offline inventory tasks can
proceed.

### Concepts Learned

- Absolute paths with spaces can be split incorrectly when launching a
  background process; use relative output paths or explicit quoting.
- Safe gzip verification needs newline preservation on Windows when comparing
  fetched HTML text after a write/read round trip.
- A post-run dry-run is a simple independent check that cache coverage is
  complete without making additional live requests.

### Files to Read

- `reports/acquisition-2000-2025-20260530.json`
- `progress/current.md`
- `progress/review.md`
- `src/nba_data/scraping/nba_team_season_acquisition.py`

### How to Test

Run `uv run nba-data acquisition dry-run-nba-team-seasons` to verify all 775
entries are cache hits. Run `uv run pytest tests/unit/test_nba_team_season_acquisition.py`
to verify the acquisition command safeguards.

### Validation

- Focused acquisition tests after the safe-write fix: passed, 19 passed.
- Post-run dry-run: 775 cache hits, 0 missing, 0 estimated fetches.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 132 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 132
  passed, 1 skipped, and 6 Peewee deprecation warnings.

### Outcome

- Acquisition report completed with 775 processed entries, 2 cache hits, 773
  fetched entries, 0 failures, and 0 rate-limited entries.
- `F4D-ACQ-LIVE-001` remains `needs_review`.

## Checkpoint 56 - F4D-ACQ-LIVE-001 Review Closure

### What Changed

Reviewed and closed `F4D-ACQ-LIVE-001` as `done`. Moved `F4D-ACQ-002` to
`ready` as the next acquisition report and cache coverage handoff task.

### Why

The controlled acquisition command and saved report satisfy the approved
Phase 4D-A live acquisition criteria, and cache coverage is complete enough to
handoff into a formal coverage review before inventory work begins.

### Concepts Learned

- Closure should preserve stopped-run context even when the final run
  succeeds.
- A saved acquisition report plus local cache artifact checks can approve the
  checkpoint without another network request.
- Handoff tasks should become `ready`, not `approved`, after a sensitive-gate
  acquisition closes.

### Files to Read

- `progress/review.md`
- `progress/history.md`
- `docs/roadmap/CURRENT_PHASE.md`
- `tasks/feature-list.json`

### How to Test

Run `python -m json.tool tasks/feature-list.json`, `uv run ruff check .`,
`uv run pytest`, and
`C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`.

### Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 132 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  132 passed, 1 skipped, and 6 Peewee deprecation warnings.

### Outcome

- `F4D-ACQ-LIVE-001` is `done`.
- `F4D-ACQ-002` is `ready`.
