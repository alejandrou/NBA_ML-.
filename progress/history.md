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

## Phase 2 F2-LIVE-001 Controlled Smoke Test

- Owner explicitly approved running one live request for
  `https://www.basketball-reference.com/teams/BOS/2024.html`.
- Promoted `F2-LIVE-001` from `pending` to `approved` to `in_progress`.
- Confirmed the smoke test still routed through `BasketballReferenceClient`;
  the injected `OneRequestHttpClient` acted only as a one-request fuse and
  printed the HTTP status.
- Cache state before execution: miss.
- Live requests: 1.
- HTTP status: 200.
- HTML chars: 928025.
- Cache path:
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`.
- Cache exists after execution: `True`.
- Parsed tables: `['advanced', 'roster', 'totals']`.
- Legacy scraper rows: roster 19, totals 19, advanced 19.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 29 passed, 3 Peewee deprecation warnings.
- Moved `F2-LIVE-001` to `needs_review`.
- Did not run historical scraping, use concurrency, request any other URL,
  write DB data, migrate the database, remove Peewee/legacy code, or implement
  API/frontend/OVR work.

## Phase 2 F2-LIVE-001 Continuation Handoff

- Current branch: `feature/fase-1-foundations`.
- Latest commits: `499d613 Close F2-004 review` and
  `33232cc Run F2-LIVE-001 smoke test`.
- Current task state: `F2-LIVE-001` is `needs_review`, not `done`.
- Next safe action: review the F2-LIVE-001 result and either close it as
  `done` or request changes.
- Do not rerun the live request unless the owner explicitly approves another
  live request and exact URL.
- Do not start `F2-005`, `F2-006`, or any other task without explicit owner
  approval.

Suggested continuation prompt:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Branch: feature/fase-1-foundations

Trabaja en modo seguro.

Primero sigue el startup protocol:
1. Lee AGENTS.md.
2. Ejecuta C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh
3. Lee docs/ai/WORKFLOW_PROTOCOL.md.
4. Lee docs/roadmap/PHASE_GOVERNANCE.md.
5. Lee docs/roadmap/CURRENT_PHASE.md.
6. Lee specs/phases/phase-2-scraper-cache-integration.md.
7. Lee tasks/feature-list.json.
8. Lee progress/current.md, progress/history.md y progress/review.md.
9. Revisa git status.

Contexto:
- F2-004 está done.
- F2-LIVE-001 fue ejecutada una sola vez para:
  https://www.basketball-reference.com/teams/BOS/2024.html
- Resultado registrado:
  - cache miss antes de ejecutar;
  - live_requests=1;
  - http_status=200;
  - html_chars=928025;
  - cache path:
    data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz
  - cache_exists_after=True;
  - parsed_tables=['advanced', 'roster', 'totals'];
  - legacy_roster_rows=19;
  - legacy_totals_rows=19;
  - legacy_advanced_rows=19.
- Validaciones posteriores registradas:
  - uv run ruff check .: passed.
  - uv run pytest: 29 passed, 3 Peewee deprecation warnings.
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed.
- F2-LIVE-001 está en needs_review, no done.
- La rama contiene estos commits locales:
  - 499d613 Close F2-004 review
  - 33232cc Run F2-LIVE-001 smoke test

Restricciones:
- No rerun live request.
- No contactes Basketball Reference.
- No escribas DB.
- No migres DB.
- No borres Peewee ni legacy.
- No implementes API/frontend/OVR.
- No empieces F2-005, F2-006 ni otra tarea sin aprobación explícita.
- No hagas reset, checkout ni descartes cambios locales.

Tarea:
- Revisa el estado de F2-LIVE-001 desde los archivos.
- Resume si cumple aceptación.
- Si está correcto, prepara el cierre de F2-LIVE-001 como done con docs/progress
  actualizados y validaciones offline.
- Si encuentras algún problema, deja F2-LIVE-001 en changes_requested y explica
  el mínimo fix.
```

## Phase 2 F2-LIVE-001 Cached Result Inspection

- Inspected the cached BOS 2024 team-season HTML at
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`.
- Used `CachedTeamSeasonHtmlProvider` with a no-network HTTP transport fuse, so
  the adapted legacy parser path was exercised through a forced cache hit.
- Cache result: hit.
- Network requests: 0.
- Cache file size: 141649 bytes.
- HTML chars: 928025.
- Detected and exported all expected tables: roster, totals, and advanced.
- Row counts: roster 19, totals 19, advanced 19.
- Exported local inspection artifacts under
  `data/exports/smoke-tests/BOS-2024/`: `roster.json`, `totals.json`,
  `advanced.json`, and `summary.md`.
- `data/exports` is not currently ignored by Git, so the exported artifacts
  must not be staged or committed unless the owner explicitly approves.
- No live request was made, no database write or migration was performed, no
  historical scraping was run, and no legacy/Peewee code was deleted.

## Phase 2 F2-LIVE-001 Review Closure

- Reviewed `F2-LIVE-001` against its acceptance criteria and approved closure.
- Verified `F2-004` was done before execution.
- Verified the owner-approved URL was
  `https://www.basketball-reference.com/teams/BOS/2024.html`.
- Verified exactly one live request was made, with HTTP status 200.
- Verified the fetched HTML was stored as
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`.
- Verified the adapted legacy scraper path could read the fetched/cached HTML:
  roster 19 rows, totals 19 rows, advanced 19 rows.
- Verified the request went through `BasketballReferenceClient` and `HtmlCache`
  with the one-request transport fuse used only to enforce the request limit.
- Verified no DB writes, DB migrations, historical scraping, concurrency,
  extra URLs, Peewee/legacy deletion, API/frontend/OVR work, or 429 retry
  occurred.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 29 passed, 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed.
- Marked `F2-LIVE-001` as `done`.
- Left `F2-005`, `F2-006`, and later tasks pending until explicit owner
  approval.

## Phase 2 F2-005 Loader Strategy Closure

- Owner approved closing the remaining Phase 2 planning tasks.
- Moved `F2-005` through `approved`, `in_progress`, `needs_review`, and `done`.
- Added `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`.
- Documented target loader boundaries: cached HTML, pure parsers, normalizers,
  validators, and future idempotent loaders.
- Documented natural keys, rerun behavior, duplicate-key validation, `TOT` as an
  aggregate rather than a team, and the rule that `player_name` is not a stable
  primary key.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- Marked `F2-005` as `done`.
- Did not run live scraping, contact Basketball Reference, write DB data,
  apply migrations, implement loaders, delete Peewee/legacy code, or implement
  API/frontend/OVR work.

## Phase 2 F2-006 Core Migration Plan Closure

- Moved `F2-006` through `approved`, `in_progress`, `needs_review`, and `done`.
- Added `docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`.
- Documented SQLAlchemy core migration planning for teams, players, and seasons
  without applying an Alembic migration.
- Documented Peewee coexistence boundaries and future Phase 4 migration steps.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- Marked `F2-006` as `done`.
- Did not write DB data, apply migrations, delete Peewee/legacy code, or
  activate Phase 3.

## Phase 2 Conservative Cleanup Audit

- Audited imports, tracked legacy folders, dependencies, docs, config, and CI.
- Confirmed `scrap/`, `models/`, `db_manager/`, `utils/`, `peewee`, `requests`,
  and `httpx` still have active legacy or test references and were not removed.
- Confirmed `tenacity` has no active imports outside lock/data, but left it in
  place because dependency removal was out of scope and `uv.lock` must not be
  edited manually.
- Confirmed `.github/workflows/ci.yml` still runs `uv sync --all-groups`,
  Ruff, and Pytest without live scraping.
- Deleted no folders, removed no dependencies, and did not edit `uv.lock`.

## Phase 2 Closure

- Marked `phase-2-scraper-cache-integration` as `done`.
- Left `current_phase_id` set to `phase-2-scraper-cache-integration`.
- Left Phase 3 tasks as `pending`; Phase 3 was not activated.
- Updated phase, task, progress, review, migration, README, and learning docs.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed.
- Did not run live scraping, contact Basketball Reference, write DB data,
  apply migrations, delete data, delete legacy/Peewee code, remove
  dependencies, edit `uv.lock`, create a branch/PR, or implement
  API/frontend/OVR work.

## Main Backup And Foundations PR Merge

- Created `legacy` from current `origin/main` at commit `f907e28`.
- Prepared `feature/fase-1-foundations` for the main PR by preserving the
  recent main cleanup and avoiding reintroduction of `etl/extract.py`,
  `ml_main.py`, and `etl_process.ipynb`.
- Pushed `feature/fase-1-foundations` at commit `8ef3572`.
- Fast-forwarded and pushed `feature/fase-3-parser-normalization` to the same
  commit `8ef3572`, without activating Phase 3.
- Opened PR #3, `Platform foundations and Phase 2 scraper-cache closure`, from
  `feature/fase-1-foundations` to `main`.
- PR #3 passed GitHub checks and was merged into `main` with merge commit
  `7ff8e2a`.
- After merge, remote `feature/fase-1-foundations` was deleted; local branch
  still exists and tracks a gone upstream.
- Current working branch is `feature/fase-3-parser-normalization`.
- `origin/main` now points to `7ff8e2a`; `origin/legacy` remains at `f907e28`.
- Phase 2 remains `done`; Phase 3 remains inactive and F3 tasks remain
  `pending`.
- Did not run live scraping, contact Basketball Reference, write DB data,
  apply migrations, delete legacy/Peewee code, remove dependencies, or
  implement API/frontend/OVR work during the branch/PR preparation.

Suggested continuation prompt:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Current branch expected: feature/fase-3-parser-normalization

Trabaja en modo seguro.

Primero sigue el startup protocol:
1. Lee AGENTS.md.
2. Ejecuta C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh
3. Lee docs/ai/WORKFLOW_PROTOCOL.md.
4. Lee docs/roadmap/PHASE_GOVERNANCE.md.
5. Lee docs/roadmap/CURRENT_PHASE.md.
6. Lee specs/phases/phase-2-scraper-cache-integration.md.
7. Lee tasks/feature-list.json.
8. Lee progress/current.md, progress/history.md, progress/review.md y progress/blockers.md.
9. Revisa git status, ramas locales/remotas y el estado de PR #3.

Contexto confirmado al 2026-05-20:
- Phase 2 esta cerrada y mergeada a main.
- PR #3, "Platform foundations and Phase 2 scraper-cache closure", esta merged:
  https://github.com/alejandrou/NBA_ML-./pull/3
- Merge commit en origin/main: 7ff8e2a.
- Backup legacy apunta al main pre-PR: f907e28.
- feature/fase-3-parser-normalization apunta a 8ef3572 y fue creada como base limpia para Phase 3.
- La rama remota feature/fase-1-foundations fue borrada despues del merge.
- current_phase_id debe seguir siendo phase-2-scraper-cache-integration.
- current_phase_status debe seguir siendo done.
- F2-001, F2-002, F2-003, F2-004, F2-LIVE-001, F2-005 y F2-006 deben estar done.
- F3-001, F3-002 y F3-003 deben seguir pending.
- No debe haber tareas approved, in_progress ni needs_review.

Restricciones:
- No live scraping.
- No contactar Basketball Reference.
- No ejecutar python scrape_main.py.
- No escribir DB.
- No aplicar migraciones.
- No borrar Peewee ni legacy.
- No borrar dependencias ni carpetas.
- No editar uv.lock manualmente.
- No activar Phase 3 sin aprobacion explicita.
- No crear rama, commit, push ni PR sin aprobacion explicita.
- No reset, checkout, clean, stash ni descartar cambios locales.

Tarea:
- Confirma desde archivos y Git que Phase 2 sigue cerrada, PR #3 esta merged y Phase 3 sigue blindada como pending/no activa.
- Resume el estado de ramas: origin/main, origin/legacy y feature/fase-3-parser-normalization.
- Si todo esta consistente, propon el siguiente paso seguro para activar Phase 3, pero espera aprobacion explicita antes de cambiar CURRENT_PHASE.md, tasks/feature-list.json o implementar F3.
```

## Phase 3 Parser Normalization

- Owner explicitly approved the transition to
  `phase-3-parser-normalization` and implementation of `F3-001`, `F3-002`,
  and `F3-003` in one offline pass.
- Activated Phase 3 and completed all three Phase 3 tasks while leaving Phase
  4 inactive.
- Expanded `parse_team_season_page` with an explicit supported table mapping:
  roster, totals, per-game, per-minute, per-possession, advanced, shooting,
  adjusted shooting, and play-by-play.
- Preserved parser purity: parser inputs are HTML strings and parser code does
  not touch network or database state.
- Added extraction of `basketball_reference_player_id` from Basketball
  Reference player links.
- Added separated team-season normalization with league, season, team, source
  table, stat scope, player identifier, identifier status, and conservative
  scraped values.
- Added offline data-quality checks for missing context, `TOT` aggregate
  classification, missing stable player IDs, duplicate natural keys, and
  required empty tables.
- Added compact fixture-based tests under `tests/fixtures/html/`; tests do not
  depend on `data/raw/html`.
- Documented parser, normalizer, and validator assumptions in
  `docs/validation/TEAM_SEASON_PIPELINE.md`.
- Did not run live scraping, contact Basketball Reference, write DB data,
  apply migrations, delete legacy/Peewee code, edit smoke-test exports, create
  a branch/PR, commit, push, or implement API/frontend/OVR work.

## Phase 3 Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.

## Phase 4A Legacy Scraper Consolidation Backlog

- Added `phase-4a-legacy-scraper-consolidation` as a proposed future phase
  before Phase 4 SQLAlchemy migration and before any controlled raw HTML
  backfill.
- Added `F4A-001` as a pending task to consolidate legacy player/team-season
  scrapers behind cache-first providers.
- Added `F4A-002` as a pending task to design bounded offline cached HTML
  processing.
- Added the Phase 4A phase spec and `F4A-001` feature spec.
- Added ADR 0015 documenting sequential/cache-first live acquisition and
  bounded offline-only concurrency.
- Updated roadmap and progress docs so the next recommended transition is
  Phase 4A while keeping `current_phase_id` as `phase-3-parser-normalization`
  and `current_phase_status` as `done`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- Did not activate Phase 4A or Phase 4, approve any tasks, run live scraping,
  contact Basketball Reference, write DB data, apply migrations, delete
  legacy/Peewee code, create a branch/PR, or implement API/frontend/OVR work.

## Phase 4A F4A-000 Parity Strategy Gate

- Added `F4A-000` as a pending Phase 4A gate before `F4A-001`.
- Created the feature spec for offline legacy-vs-new parser parity and a
  manual one-page live acquisition smoke-test strategy.
- Added `depends_on: ["F4A-000"]` to `F4A-001` while keeping `F4A-001` and
  `F4A-002` pending.
- Added ADR 0016 for live-vs-offline validation and updated ADR 0004 with
  manual smoke-test rate-limit rules.
- Updated roadmap/default-decision docs so parser/refactor correctness is
  validated offline, while live smoke tests remain owner-approved and
  shape-only.
- Kept `current_phase_id` as `phase-3-parser-normalization` and
  `current_phase_status` as `done`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, write DB data,
  apply migrations, run controlled backfill, activate Phase 4A, approve tasks,
  create a branch/PR, or implement API/frontend/OVR work.

## Phase 3 Continuation Handoff

Use this prompt to continue in a fresh Codex window:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Current branch expected: feature/fase-3-parser-normalization

Actua como implementer + reviewer del repo.

Primero sigue el startup protocol:
1. Lee AGENTS.md.
2. Ejecuta C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh
3. Lee docs/ai/WORKFLOW_PROTOCOL.md.
4. Lee docs/roadmap/PHASE_GOVERNANCE.md.
5. Lee docs/roadmap/CURRENT_PHASE.md.
6. Lee tasks/feature-list.json.
7. Lee specs/phases/phase-3-parser-normalization.md.
8. Lee progress/current.md, progress/history.md, progress/review.md y progress/blockers.md.
9. Revisa git status.

Contexto confirmado al 2026-05-20:
- Phase 3 esta implementada, validada y marcada done.
- current_phase_id debe ser phase-3-parser-normalization.
- current_phase_status debe ser done.
- F3-001, F3-002 y F3-003 deben estar done.
- No debe haber tareas approved, in_progress ni needs_review.
- Phase 4 no esta activa; F4-001, F4-002 y F4-003 deben seguir pending.
- Validacion Phase 3:
  - python -m json.tool tasks/feature-list.json: passed.
  - uv run ruff check .: passed.
  - uv run pytest: passed, 43 passed and 3 Peewee deprecation warnings.
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed.
  - C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh: passed.
- Parser soporta roster, totals, per_game, per_minute, per_poss, advanced, shooting, adj_shooting y pbp.
- Normalizer y validator estan separados del parser.
- TOT se maneja como aggregate, no como equipo real.
- player_name no se usa como stable primary key.
- No se hizo live scraping, no se contacto Basketball Reference, no hubo DB writes, no hubo migraciones, no se borro legacy/Peewee, no hubo API/frontend/OVR, y no se hizo commit/push/PR.

Restricciones:
- No live scraping.
- No contactar Basketball Reference.
- No ejecutar python scrape_main.py.
- No escribir DB.
- No aplicar migraciones.
- No borrar Peewee ni legacy.
- No borrar data/raw/html ni exports smoke.
- No implementar API/frontend/OVR/rankings/similarity/ML.
- No crear branch, commit, push ni PR sin aprobacion explicita del owner.
- No activar Phase 4 ni aprobar F4 tasks sin aprobacion explicita del owner.
- No reset, checkout, clean, stash ni descartar cambios locales.

Tarea:
- Confirma desde archivos y Git que Phase 3 sigue cerrada y validada.
- Resume el working tree y los archivos modificados.
- Propone el siguiente paso seguro: pedir aprobacion explicita para activar phase-4-sqlalchemy-migration o, si el owner lo pide expresamente, preparar publicacion/commit/PR de Phase 3.
- No implementes Phase 4 todavia.
```

## Phase 4A F4A-000 Activation And Review Closure

- Created local branch `feature/fase-4a-legacy-scraper-consolidation` from
  `b2c9960cc969bfc4c718cffd6534e6a46245704e`.
- Activated `phase-4a-legacy-scraper-consolidation` without activating Phase 4
  SQLAlchemy migration.
- Marked `F4A-000` as `done` after reviewing its existing feature spec and
  ADR coverage.
- Kept `F4A-001`, `F4A-002`, `F4-001`, `F4-002`, and `F4-003` as `pending`.
- Confirmed the strategy covers offline legacy-vs-new parser parity, frozen or
  fixture-copied cached HTML, golden fixtures, roster/totals/advanced
  comparison, manual one-page live smoke-test rules, `BasketballReferenceClient`
  plus `HtmlCache`, 10 requests/minute default, 20 requests/minute maximum,
  HTTP 429 stop behavior, no DB writes, no historical scraping, no live
  concurrency, and bounded concurrency only for already-cached local HTML in
  future tasks.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 43 passed and 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, run controlled
  backfill, write DB data, apply migrations, delete legacy/Peewee code, start
  `F4A-001` or `F4A-002`, activate Phase 4 SQLAlchemy migration, commit, push,
  open a PR, or implement API/frontend/OVR work.
- Left the pre-existing local change in
  `specs/phases/phase-2-scraper-cache-integration.md` untouched.

## Phase 4A Continuation Handoff

Use this prompt to continue in a fresh Codex window:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Current branch expected: feature/fase-4a-legacy-scraper-consolidation
Current HEAD expected: b2c9960cc969bfc4c718cffd6534e6a46245704e

Actua como owner/leader + implementer/reviewer del repo.

Primero sigue el startup protocol:
1. Lee AGENTS.md.
2. Ejecuta "C:\Program Files\Git\bin\bash.exe" scripts/harness/init.sh
3. Lee docs/ai/WORKFLOW_PROTOCOL.md.
4. Lee docs/roadmap/PHASE_GOVERNANCE.md.
5. Lee docs/roadmap/CURRENT_PHASE.md.
6. Lee tasks/feature-list.json.
7. Lee specs/phases/phase-4a-legacy-scraper-consolidation.md.
8. Lee specs/features/F4A-000-legacy-parity-and-acquisition-smoke-test-strategy.md.
9. Lee docs/decisions/0016-live-vs-offline-validation.md,
   docs/decisions/0015-live-vs-offline-concurrency.md y
   docs/decisions/0004-rate-limited-scraping.md.
10. Lee progress/current.md, progress/history.md, progress/review.md y
    progress/blockers.md.
11. Revisa git status, git branch --show-current y git rev-parse HEAD.

Contexto confirmado:
- Phase 4A esta activa.
- current_phase_id debe ser phase-4a-legacy-scraper-consolidation.
- current_phase_status debe ser in_progress.
- F4A-000 debe estar done.
- F4A-001 debe seguir pending y depende de F4A-000.
- F4A-002 debe seguir pending.
- F4-001, F4-002 y F4-003 deben seguir pending.
- No debe haber tareas approved, in_progress ni needs_review.
- Validacion F4A-000:
  - python -m json.tool tasks/feature-list.json: passed.
  - uv run ruff check .: passed.
  - uv run pytest: passed, 43 passed and 3 Peewee deprecation warnings.
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed.
  - C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh: passed.
- F4A-000 cerro solo la estrategia de parity offline y smoke manual; no
  implemento consolidacion legacy.
- La branch local fue creada desde b2c9960cc969bfc4c718cffd6534e6a46245704e.
- Hay cambios locales de documentacion/estado de Phase 4A sin commit.
- El cambio local preexistente en specs/phases/phase-2-scraper-cache-integration.md
  no pertenece a F4A-000; no lo edites, no lo reviertas y no lo incluyas en
  ningun commit salvo aprobacion explicita del owner.

Restricciones:
- No live scraping.
- No contactar Basketball Reference.
- No ejecutar python scrape_main.py.
- No controlled raw HTML backfill.
- No escribir DB real/dev.
- No aplicar migraciones.
- No borrar datos, raw HTML, exports, legacy ni Peewee.
- No implementar API/frontend/OVR/rankings/similarity/ML.
- No activar Phase 4 SQLAlchemy migration.
- No aprobar ni empezar F4A-001, F4A-002 ni tareas F4 sin aprobacion explicita.
- No crear commit, push ni PR sin aprobacion explicita.
- No reset, checkout, clean, stash ni descartar cambios locales.

Tarea inicial:
- Confirma desde archivos y Git que Phase 4A esta activa, F4A-000 esta done y
  no hay tareas aprobadas/en progreso/en review.
- Resume el working tree y distingue los cambios de F4A-000 del cambio
  preexistente en specs/phases/phase-2-scraper-cache-integration.md.
- Propone el siguiente paso seguro: pedir aprobacion explicita para promover
  F4A-001, o pedir aprobacion para preparar commit/PR de la activacion de
  Phase 4A y cierre de F4A-000.
- No implementes F4A-001 todavia.
```

## Phase 4A F4A-002 Spec Repair And Review Closure

- Promoted `F4A-002` for the owner-approved documentation/design repair.
- Created
  `specs/features/F4A-002-bounded-offline-cached-html-processing.md`.
- Updated `tasks/feature-list.json` so `F4A-002` includes the feature-spec
  acceptance criterion and is marked `done` after validation.
- Documented the offline-only target flow:
  `cached .html.gz -> parse_team_season_page -> normalize_team_season_page -> validate_normalized_team_season_rows -> future Phase 4 idempotent loader boundary`.
- Specified that a future offline processor accepts no
  `BasketballReferenceClient`, `httpx`, `requests`, or generic network client,
  and fails on cache miss instead of refreshing cache.
- Documented bounded execution defaults: sequential with `max_workers=1`,
  threads only for bounded local gzip/read/parse batches, processes only for
  profiled CPU-heavy local work, and async only as local orchestration over
  already-cached inputs.
- Delegated all DB writes to later Phase 4 idempotent loaders after
  validation.
- Kept `F4A-001`, `F4-001`, `F4-002`, and `F4-003` as `pending`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 43 passed and 3 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- Did not implement a runtime offline processor, run live scraping, contact
  Basketball Reference, run controlled backfill, write DB data, apply
  migrations, delete legacy/Peewee code, start `F4A-001`, activate Phase 4
  SQLAlchemy migration, commit, push, open a PR, or implement API/frontend/OVR
  work.
- Left the pre-existing local change in
  `specs/phases/phase-2-scraper-cache-integration.md` untouched.

## Phase 4A F4A-001 Legacy Scraper Consolidation

- Promoted and implemented `F4A-001` with owner approval from the current
  request.
- Added a generic cache-first Basketball Reference page provider and URL
  builders for `/teams/`, `/teams/{TEAM}/{YEAR}.html`, and
  `/teams/{TEAM}/{YEAR}_games.html`.
- Kept `CachedTeamSeasonHtmlProvider` and cached team-season parsing
  compatibility.
- Added `LegacyTeamSeasonTableAdapter` so roster, totals, and advanced player
  scrapers can share one HTML read and one parsed team-season page per
  team/year.
- Refactored legacy player roster, totals, and advanced scrapers to remove
  direct `httpx` paths, manual sleeps, and `asyncio.gather` live fan-out.
- Refactored included team scrapers so `/teams/` and `_games.html` pages use
  the generic cache-first provider instead of direct `requests.get` or direct
  async HTTP usage.
- Updated `scrape_main.py` wiring to build `HtmlCache`,
  `BasketballReferenceClient`, `CachedBasketballReferencePageProvider`, and
  `CachedTeamSeasonHtmlProvider` centrally. The entrypoint was not executed.
- Added offline fixtures and unit tests for provider caching, shared player
  adapter reuse, legacy-compatible row keys, and team scraper provider wiring.
- Marked `F4A-001` as `done` after validation.
- Kept `F4-001`, `F4-002`, and `F4-003` as `pending`; Phase 4 SQLAlchemy
  migration remains inactive.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 55 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 55 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, run controlled
  backfill, write DB data, apply migrations, delete legacy/Peewee code,
  activate Phase 4 SQLAlchemy migration, commit, push, open a PR, or implement
  API/frontend/OVR work.
- Left untracked `project.zip` untouched.

## Phase 4B/4C Roadmap Transition

- Confirmed `F4A-001` is `done` in `tasks/feature-list.json` before changing
  the current phase.
- Confirmed no task was `approved` or `in_progress`.
- Moved `current_phase_id` to `phase-4b-controlled-raw-html-backfill` and
  `current_phase_status` to `proposed`.
- Kept `F4B-001` as `ready` with no approved or in-progress task.
- Added Phase 4B tasks for manifest design, dry-run validation, sequential
  cache-first acquisition, and an owner-approved pilot.
- Added Phase 4C tasks for offline cached HTML processing, idempotent DB load
  integration, and reporting/quarantine workflow.
- Added phase specs for Phase 4B and Phase 4C.
- Updated roadmap, current progress, next decisions, Phase 4A closure, and
  Phase 4 SQLAlchemy handoff documentation.
- Clarified that `IDEMPOTENT_LOADER_STRATEGY.md` does not download or parse raw
  HTML.
- Clarified that `TEAM_SEASON_PIPELINE.md` documents parsing, normalization,
  and validation from already available HTML, and that player-specific pages
  are future scope.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 55 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, run controlled
  backfill, write DB data, apply migrations, delete legacy/Peewee code,
  approve or start any task, commit, push, open a PR, or implement
  API/frontend/OVR work.

## Phase 4B F4B-001 Manifest Design

- Owner explicitly approved implementing `F4B-001` only.
- Promoted `F4B-001` through the workflow and closed it as `done` after
  validation and review.
- Created
  `specs/features/F4B-001-controlled-raw-html-backfill-manifest.md`.
- Documented the controlled acquisition contract:
  `approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`.
- Defined the JSON manifest as a reviewed acquisition plan with explicit
  Basketball Reference URLs, page types, approval metadata, cache-first
  behavior, sequential execution, 10 requests/minute default, 20
  requests/minute absolute maximum, and `.html.gz` writes through `HtmlCache`.
- Set the initial pilot default to at most five `team_season` URLs matching
  `/teams/{TEAM}/{YEAR}.html`.
- Documented that player-specific pages are outside the initial pilot unless a
  later explicit task and manifest approve them.
- Documented that any live request requires owner approval for the exact
  manifest and that any manifest change requires fresh approval.
- Kept `F4B-002`, `F4B-003`, `F4B-LIVE-001`, `F4-001`, `F4-002`, `F4-003`,
  and `F4C-*` tasks `pending`.
- Kept `current_phase_id` as `phase-4b-controlled-raw-html-backfill` and
  `current_phase_status` as `proposed`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 55 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 55 passed and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, implement a runtime
  backfill runner, write DB data, apply migrations, run parse/load offline,
  activate Phase 4 SQLAlchemy migration or Phase 4C, delete legacy/Peewee code,
  commit, push, open a PR, or implement API/frontend/OVR work.

## Phase 4B F4B-002 Manifest Dry-Run Validation

- Owner explicitly approved implementing `F4B-002` only.
- Promoted `F4B-002` from `pending` to `in_progress` and then to
  `needs_review` after implementation and focused validation.
- Added offline raw HTML backfill manifest validation for approved
  `team_season` manifests.
- The validation requires owner approval metadata, explicit Basketball
  Reference team-season URLs, no duplicate URLs, cache-first sequential policy,
  safe request limits, and `HtmlCache .html.gz` as the write target.
- Added dry-run reporting for planned URLs, page types, expected cache paths,
  cache hit/miss state, and estimated live request count.
- Added `nba-data backfill dry-run <manifest.json>` as an offline CLI utility.
- Added local manifest fixtures and unit tests for valid dry-runs, unapproved
  manifests, duplicate URLs, unsupported URLs, unsafe policies, pilot size, and
  the no-client dry-run boundary.
- Kept `F4B-003`, `F4B-LIVE-001`, Phase 4 SQLAlchemy tasks, and Phase 4C
  tasks `pending`.
- Kept `current_phase_id` as `phase-4b-controlled-raw-html-backfill` and
  `current_phase_status` as `proposed`.
- Ran `uv run pytest tests/unit/test_backfill_manifest.py`: passed, 8 passed.
- Ran `uv run ruff check src/nba_data/scraping/backfill_manifest.py src/nba_data/cli/main.py tests/unit/test_backfill_manifest.py`:
  passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 63 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 63 passed and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, implement the
  runtime acquisition runner, write raw HTML outside temporary test cache,
  write DB data, apply migrations, run parse/load offline, activate Phase 4
  SQLAlchemy migration or Phase 4C, delete legacy/Peewee code, commit, push,
  open a PR, or implement API/frontend/OVR work.

## Phase 4B F4B-002 Review Closure

- Reviewed and approved `F4B-002`.
- Confirmed the dry-run manifest path validates approved `team_season`
  manifests and reports planned URLs, expected cache paths, cache hit/miss
  state, and estimated live request count.
- Confirmed the dry-run path does not accept a network client and does not
  contact Basketball Reference.
- Ran `uv run pytest tests/unit/test_backfill_manifest.py`: passed, 8 passed.
- Ran `uv run ruff check src/nba_data/scraping/backfill_manifest.py src/nba_data/cli/main.py tests/unit/test_backfill_manifest.py`:
  passed.
- Marked `F4B-002` as `done`.
- Did not run live scraping, contact Basketball Reference, execute the
  acquisition runner, write raw HTML outside temporary test cache, write DB
  data, apply migrations, start a live pilot, delete legacy/Peewee code, commit,
  push, open a PR, or implement API/frontend/OVR work.

## Phase 4B F4B-003 Acquisition Runner

- Owner explicitly approved implementing `F4B-003` only; `F4B-LIVE-001`
  remains pending.
- Promoted `F4B-003` from `pending` to `in_progress` and then to
  `needs_review` after implementation and focused validation.
- Added a sequential cache-first acquisition runner for approved manifests.
- The runner checks `HtmlCache` before every client request, records cache hits
  without network calls, fetches cache misses through an injected
  `BasketballReferenceClient`-compatible client, and stores fetched HTML through
  `HtmlCache`.
- Added acquisition result/report serialization, including processed entries,
  cache hits, fetched pages, failures, live request count, and per-entry
  statuses.
- Added failure handling that stops the run and exposes a partial acquisition
  report.
- Added `nba-data backfill acquire <manifest.json> --execute-approved-manifest`
  with an explicit execution flag. The CLI constructs `HtmlCache` and
  `BasketballReferenceClient`, but tests patch the client with fakes.
- Added offline unit tests for approved-manifest enforcement, cache hits, cache
  misses, sequential order, partial failure reports, CLI refusal without the
  execution flag, and fake-client CLI acquisition.
- Kept `F4B-LIVE-001`, Phase 4 SQLAlchemy tasks, and Phase 4C tasks `pending`.
- Kept `current_phase_id` as `phase-4b-controlled-raw-html-backfill` and
  `current_phase_status` as `proposed`.
- Ran `uv run pytest tests/unit/test_backfill_manifest.py`: passed, 15 passed.
- Ran `uv run ruff check src/nba_data/scraping/backfill_manifest.py src/nba_data/cli/main.py tests/unit/test_backfill_manifest.py`:
  passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 70 passed and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, run a live backfill,
  write raw HTML outside temporary test cache, write DB data, apply migrations,
  run parse/load offline, activate Phase 4 SQLAlchemy migration or Phase 4C,
  delete legacy/Peewee code, commit, push, open a PR, or implement
  API/frontend/OVR work.

## Phase 4B F4B-003 Commit/Push Handoff

- Prepared the `F4B-003` implementation, review notes, task status, roadmap
  notes, progress files, and tests for commit and push on
  `feature/fase-4a-legacy-scraper-consolidation`.
- Current task state for the next session: `F4B-003` is `needs_review`;
  `F4B-LIVE-001` remains `pending`.
- Next safe action after push: review `F4B-003` and either close it as `done`
  after approval or request changes.
- Do not run the acquisition runner against Basketball Reference, approve or
  run `F4B-LIVE-001`, write DB data, apply migrations, delete legacy/Peewee
  code, open a PR, or implement API/frontend/OVR work without explicit owner
  approval.

## Phase 4B F4B-003 Review Closure

- Owner approved closing `F4B-003` as `done`.
- Reviewed the sequential cache-first acquisition runner against the Phase 4B
  acceptance criteria.
- Confirmed the runner validates approved manifests, checks `HtmlCache` before
  every client request, records cache hits without network calls, fetches cache
  misses through a `BasketballReferenceClient`-compatible client, writes only
  through `HtmlCache`, and returns partial reports on client failure.
- Marked `F4B-003` as `done`.
- Marked `F4B-LIVE-001` as `ready` so the exact pilot manifest can be prepared
  and reviewed.
- Kept `current_phase_id` as `phase-4b-controlled-raw-html-backfill` and
  `current_phase_status` as `proposed`.
- Kept Phase 4 SQLAlchemy migration and Phase 4C tasks `pending`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 70 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, execute
  `nba-data backfill acquire`, run a live pilot, write DB data, apply
  migrations, parse/load offline data, activate Phase 4 SQLAlchemy migration
  or Phase 4C, delete legacy/Peewee code, create a branch, push, open a PR, or
  implement API/frontend/OVR work.

## Phase 4B F4B-LIVE-001 Raw HTML Backfill Pilot

- Owner explicitly approved implementing the exact two-URL manifest:
  `tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`.
- Promoted `F4B-LIVE-001` from `ready` to `in_progress` while keeping
  `current_phase_status` as `proposed`.
- Ran the offline dry-run before live acquisition.
- Pre-run dry-run result: 2 total entries, 1 cache hit, 1 cache miss, and 1
  estimated live request.
- BOS 2024 was a cache hit at
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`.
- DEN 2023 was a cache miss before acquisition at
  `data\raw\html\basketball-reference\teams-den-2023.html-4bfff60cb079ffe5.html.gz`.
- Ran
  `uv run nba-data backfill acquire tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json --execute-approved-manifest`.
- Acquisition result: 2 processed entries, 1 cache hit, 1 fetched page, 0
  failures, and 1 live request.
- DEN 2023 was fetched through the controlled acquisition path and stored as
  `.html.gz` in `HtmlCache`.
- DEN 2023 cache file size after acquisition: 139188 bytes.
- Post-run dry-run result: 2 cache hits, 0 cache misses, and 0 estimated live
  requests.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran
  `python -m json.tool tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`:
  passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 70 passed and 6 Peewee deprecation warnings.
- Moved `F4B-LIVE-001` to `needs_review`.
- Did not run parser/load offline processing, write DB data, apply migrations,
  run full historical scraping, use concurrency, delete raw HTML, delete
  legacy/Peewee code, activate Phase 4 SQLAlchemy migration or Phase 4C,
  create a branch, commit, push, open a PR, or implement API/frontend/OVR work.

## Phase 4B F4B-LIVE-001 Review Closure

- Reviewed `F4B-LIVE-001` against its acceptance criteria and approved closure.
- Confirmed the exact approved manifest was
  `tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`.
- Confirmed the pilot used only two approved team-season URLs:
  `https://www.basketball-reference.com/teams/BOS/2024.html` and
  `https://www.basketball-reference.com/teams/DEN/2023.html`.
- Confirmed BOS 2024 was a cache hit and DEN 2023 was fetched once through the
  controlled acquisition runner.
- Confirmed acquisition totals: 2 processed entries, 1 cache hit, 1 fetched
  page, 0 failures, and 1 live request.
- Verified the DEN 2023 cached gzip offline at
  `data\raw\html\basketball-reference\teams-den-2023.html-4bfff60cb079ffe5.html.gz`.
- Verified the DEN 2023 gzip is readable with 911464 HTML characters, contains
  the expected Denver, `roster`, `totals_stats`, and `advanced` markers, and
  does not contain the wrong-team Boston marker.
- Verified the post-run dry-run reports 2 cache hits, 0 cache misses, and 0
  estimated live requests.
- Marked `F4B-LIVE-001` as `done`.
- Kept `current_phase_id` as `phase-4b-controlled-raw-html-backfill` and
  `current_phase_status` as `proposed`.
- Confirmed no task is currently `approved`, `in_progress`, or `needs_review`.
- Kept Phase 4 SQLAlchemy migration and Phase 4C tasks `pending`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran
  `python -m json.tool tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`:
  passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 70 passed and 6 Peewee deprecation warnings.
- Did not rerun live acquisition, contact Basketball Reference, write DB data,
  apply migrations, run parser/load offline processing, start Phase 4C,
  activate Phase 4 SQLAlchemy migration, delete raw HTML, delete legacy/Peewee
  code, create a branch, commit, push, open a PR, or implement
  API/frontend/OVR work.

## Phase 4B Closure And Phase 4 SQLAlchemy Transition

- Closed `phase-4b-controlled-raw-html-backfill` after `F4B-001`, `F4B-002`,
  `F4B-003`, and `F4B-LIVE-001` were reviewed and marked `done`.
- Moved the current phase to `phase-4-sqlalchemy-migration` with status
  `proposed`.
- Promoted `F4-001` to `ready` as the next candidate task.
- Kept `F4-001` unapproved; no task is `approved`, `in_progress`, or
  `needs_review`.
- Kept `F4-002`, `F4-003`, and Phase 4C tasks `pending`.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- Ran `uv run alembic check`: failed with existing nullable drift on
  `raw.raw_pages.fetched_at`, `raw.scraper_requests.requested_at`, and
  `raw.scraper_runs.started_at`.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, execute a backfill
  runner, write DB data, apply migrations, delete raw HTML, delete
  legacy/Peewee code, create a branch, commit, push, open a PR, or implement
  API/frontend/OVR work.

## Phase 4 F4-001 Core SQLAlchemy Migration

- Owner explicitly approved implementing `F4-001` only while keeping
  `phase-4-sqlalchemy-migration` in `proposed`.
- Promoted `F4-001` from `ready` to `in_progress`, implemented it, and moved it
  to `needs_review`.
- Added the feature spec for core team/player/season SQLAlchemy migrations.
- Added additive SQLAlchemy models and Alembic revision
  `0002_core_team_player_season.py`.
- Added `core.team_seasons`, `core.player_seasons`, and
  `core.player_team_seasons` as relationship tables without stats or loaders.
- Added core unique/check constraints for stable Basketball Reference team IDs
  and `TOT`-safe real team identifiers.
- Added offline SQLAlchemy metadata tests for schemas, constraints, foreign
  keys, relationships, and model exports.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 77 passed and 6 Peewee deprecation warnings.
- Ran `uv run alembic upgrade head --sql`: passed.
- Initially, Docker/PostgreSQL was unavailable, so only offline Alembic SQL
  generation could run.
- Retried after Docker became available:
  - `docker compose up -d postgres`: passed.
  - `docker compose exec -T postgres pg_isready -U nba -d nba`: passed.
  - `uv run alembic upgrade head`: passed and applied
    `0002_core_team_player_season`.
  - `uv run alembic check`: failed only with the pre-existing nullable drift on
    `raw.raw_pages.fetched_at`, `raw.scraper_requests.requested_at`, and
    `raw.scraper_runs.started_at`; no new `core.*` drift was reported.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  77 passed and 6 Peewee deprecation warnings.
- Ran `git diff --cached --name-only -- .env data/raw`: passed with no output.
- Did not run live scraping, contact Basketball Reference, write loader data,
  delete data, apply destructive migrations, delete legacy/Peewee code, start
  `F4-002`, `F4-003`, or Phase 4C, create a branch, commit, push, open a PR, or
  implement API/frontend/OVR/ranking/similarity/ML work.

## Phase 4 F4-001 Review Closure

- Owner approved closing `F4-001` as `done`.
- Marked `F4-001` as `done`.
- Kept `F4-002` and `F4-003` unstarted until explicit approval.
- No live scraping, Basketball Reference contact, loader implementation,
  destructive migration, data deletion, Peewee/legacy deletion, branch, commit,
  push, PR, API/frontend/OVR/ranking/similarity/ML, or Phase 4C work occurred
  during review closure.

## Phase 4 F4-003 Database Integration Validation Path

- Owner approved implementing `F4-003`.
- Promoted `F4-003` from `pending` to `in_progress` and then to `needs_review`
  after validation.
- Added `specs/features/F4-003-database-integration-validation-path.md`.
- Added `scripts/harness/db-validate.sh` for local PostgreSQL validation.
- Aligned raw timestamp SQLAlchemy metadata with the existing nullable
  `0001_initial_raw_core` migration for `raw.raw_pages.fetched_at`,
  `raw.scraper_requests.requested_at`, and `raw.scraper_runs.started_at`.
- Added offline tests for raw timestamp nullable/default metadata.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 78 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  78 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`:
  passed; `alembic check` reported no new upgrade operations.
- Ran `git diff --cached --name-only -- .env data/raw`: passed with no output.
- Kept `F4-002` and Phase 4C pending.
- Did not run live scraping, contact Basketball Reference, delete or reset DB
  data, apply destructive migrations, implement loaders, delete legacy/Peewee
  code, create a branch, commit, push, open a PR, or implement
  API/frontend/OVR/ranking/similarity/ML work.

## Phase 4 F4-003 Handoff

- Prepared a continuation prompt in `progress/current.md`.
- Current task state for the next session: `F4-003` is `needs_review`.
- Next safe action: review `F4-003` and either mark it `done` after approval
  or move it to `changes_requested` with the smallest corrective fix.
- `F4-002` remains `pending` and must not start without explicit owner
  approval.

## Phase 4 F4-003 Review Closure

- Reviewed `F4-003` against its acceptance criteria and approved closure.
- Confirmed `scripts/harness/db-validate.sh` starts/checks local PostgreSQL,
  runs `uv run alembic upgrade head`, and then runs `uv run alembic check`.
- Confirmed raw timestamp metadata now matches existing nullable migration
  behavior for `raw.raw_pages.fetched_at`,
  `raw.scraper_requests.requested_at`, and `raw.scraper_runs.started_at`.
- Confirmed `alembic check` reports no new upgrade operations after applying
  migrations to local PostgreSQL.
- Confirmed offline tests cover the raw nullable/default metadata alignment
  without requiring a database or network.
- Marked `F4-003` as `done`.
- Kept `phase-4-sqlalchemy-migration` in `proposed`.
- Kept `F4-002` and Phase 4C pending until explicit owner approval.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 78 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 78 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`:
  passed; `alembic check` reported no new upgrade operations.
- Ran `uv run alembic current`: reported
  `0002_core_team_player_season (head)`.
- Ran `git diff --cached --name-only -- .env data/raw`: passed with no output.
- Did not run live scraping, contact Basketball Reference, delete or reset DB
  data, apply destructive migrations, implement loaders, delete legacy/Peewee
  code, create a branch, commit, push, open a PR, or implement
  API/frontend/OVR/ranking/similarity/ML work.

## Phase 4 F4-002 Idempotent Loader Repositories

- Owner approved implementing `F4-002` while keeping
  `phase-4-sqlalchemy-migration` in `proposed`.
- Promoted `F4-002` from `pending` to `in_progress` and then to `needs_review`
  after focused validation.
- Added `specs/features/F4-002-idempotent-loader-repositories.md`.
- Added portable SQLAlchemy core repositories using select-then-insert/update
  logic and no `session.commit()` calls.
- Added `load_team_season_core(...)` for already-normalized team-season rows.
- Loader validation and duplicate natural-key checks run before DB writes.
- Added SQLite unit tests for idempotent reruns, invalid batches, duplicate
  natural keys, no-commit behavior, rollback behavior, name overwrite rules,
  player identity, `TOT` aggregate handling, and roster values.
- Added a PostgreSQL integration smoke test that reruns the same batch twice
  through the real migrated schema and rolls back the transaction.
- Extended `scripts/harness/db-validate.sh` to run the PostgreSQL smoke test
  after `alembic upgrade head` and `alembic check`.
- Ran `uv run pytest tests/unit/test_team_season_loader.py`: passed, 9 passed.
- Ran `uv run pytest tests/integration/test_team_season_loader_postgres.py`:
  passed, 1 passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 88 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  88 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`:
  passed; `alembic check` reported no new upgrade operations and the
  PostgreSQL smoke test passed.
- Ran `uv run alembic current`: reported
  `0002_core_team_player_season (head)`.
- Ran `git diff --cached --name-only -- .env data/raw`: passed with no output.
- Kept Phase 4C pending.
- Did not run live scraping, contact Basketball Reference, delete or reset DB
  data, apply destructive migrations, delete legacy/Peewee code, create a
  branch, commit, push, open a PR, or implement
  API/frontend/OVR/ranking/similarity/ML work.

## Phase 4 F4-002 Continuation Handoff

- Current branch: `feature/fase-4-sqlalchemy-migration`.
- Task state at handoff: `F4-002` was `needs_review`.
- `F4-001` and `F4-003` are `done`.
- No task is currently `approved` or `in_progress`.
- Next safe action: review `F4-002` and either mark it `done` after approval
  or move it to `changes_requested` with the smallest corrective fix.
- Phase 4C remains pending and must not start without explicit owner approval.

## Phase 4 F4-002 Review Closure And Phase 4 Closure

- Reviewed `F4-002` against its acceptance criteria and approved closure.
- Confirmed loader validation and duplicate natural-key checks run before any
  repository writes.
- Confirmed repositories use portable SQLAlchemy `select(...)` plus
  `add/flush` logic, without dialect-specific upserts.
- Confirmed loader and repository methods do not call `session.commit()`.
- Confirmed caller-owned rollback removes inserted records, including the
  PostgreSQL smoke test transaction.
- Confirmed existing meaningful team and player names are not overwritten by
  fallback or empty values.
- Confirmed `player_name` is not used as an identity key; player identity uses
  `basketball_reference_player_id`.
- Confirmed `TOT` aggregate rows do not create real `Team`, `TeamSeason`, or
  `PlayerTeamSeason` records.
- Confirmed no new Alembic revision was added for `F4-002`; the only Phase 4
  core schema revision remains `0002_core_team_player_season.py`.
- Marked `F4-002` as `done`.
- Marked `phase-4-sqlalchemy-migration` as `done`.
- Kept Phase 4C pending until explicit owner approval.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 88 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`:
  passed, 88 passed and 6 Peewee deprecation warnings.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`:
  passed; `alembic check` reported no new upgrade operations and the
  PostgreSQL smoke test passed.
- Ran `uv run alembic current`: reported
  `0002_core_team_player_season (head)`.
- Ran `git diff --cached --name-only -- .env data/raw`: passed with no output.
- Did not run live scraping, contact Basketball Reference, start Phase 4C,
  process cached HTML, delete or reset DB data, apply destructive migrations,
  delete legacy/Peewee code, create a branch, commit, push, open a PR, or
  implement API/frontend/OVR/ranking/similarity/ML work.

## Phase 4 Merge And Phase 4C Handoff

- PR #6, `[codex] Close Phase 4 SQLAlchemy migration`, was merged into
  `main`: `https://github.com/alejandrou/NBA_ML-./pull/6`.
- GitHub CI for PR #6 passed.
- Local `main` was fast-forwarded to `origin/main` after the merge.
- Current task state: `F4-001`, `F4-002`, and `F4-003` are `done`.
- Current phase state: `phase-4-sqlalchemy-migration` is `done`.
- Phase 4C tasks remain `pending`; no Phase 4C task has been approved or
  started.
- Next safe development step is explicit owner approval to activate
  `phase-4c-offline-cached-html-processing-and-load` and select `F4C-001`.
- Do not run live scraping, contact Basketball Reference, refresh cache misses,
  write DB loader data from cached HTML, delete data, run destructive
  migrations, delete Peewee/legacy code, create a branch, commit, push, open a
  PR, or implement API/frontend/OVR/ranking/similarity/ML work without explicit
  owner approval.

Suggested continuation prompt:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Expected branch: main

Goal: continue after the merged Phase 4 SQLAlchemy migration and prepare the
next development step for Phase 4C. Follow the repo startup protocol first.

Startup protocol:
1. Read AGENTS.md.
2. Run C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh.
3. Read docs/ai/WORKFLOW_PROTOCOL.md.
4. Read docs/roadmap/PHASE_GOVERNANCE.md.
5. Read docs/roadmap/CURRENT_PHASE.md.
6. Read tasks/feature-list.json.
7. Read specs/phases/phase-4-sqlalchemy-migration.md.
8. Read specs/phases/phase-4c-offline-cached-html-processing-and-load.md.
9. Read specs/features/F4C-001-offline-cached-html-processor.md if it exists;
   if it does not exist, inspect tasks/feature-list.json and the Phase 4C spec
   before proposing the smallest spec/task-state update.
10. Read progress/current.md, progress/history.md, and progress/review.md.
11. Run git status --short --branch.

Context:
- PR #6 is merged: https://github.com/alejandrou/NBA_ML-./pull/6.
- Phase 4 is closed and merged.
- current_phase_id is phase-4-sqlalchemy-migration.
- current_phase_status is done.
- F4-001, F4-002, and F4-003 are done.
- Phase 4C remains pending/future and has not been approved yet.
- F4C-001 is the expected next candidate task:
  implement an offline cached HTML processor that reads only existing .html.gz
  cache files, parses, normalizes, and validates team-season rows without any
  network client and without database writes.

Owner approval for this session:
- I approve transitioning the roadmap from Phase 4 to
  phase-4c-offline-cached-html-processing-and-load.
- I approve preparing F4C-001 as the first Phase 4C task.
- Before implementing runtime code, inspect whether the F4C-001 feature spec
  exists and whether task state/current phase docs need a transition update.

Guardrails:
- No live scraping.
- Do not contact Basketball Reference.
- Do not refresh cache misses.
- Do not write DB loader data from cached HTML in F4C-001.
- Do not delete raw HTML, database records, volumes, Peewee, or legacy code.
- No destructive migrations.
- No API/frontend/OVR/ranking/similarity/ML.
- Do not create a branch, commit, push, or open a PR without explicit owner
  approval in that session.

Task:
1. Inspect the Phase 4C specs/tasks/progress state.
2. If source-of-truth files still point to Phase 4 as done, propose or make the
   smallest transition update to set Phase 4C as current and F4C-001 as ready
   or approved according to phase governance and the approval above.
3. Then either produce a concise implementation plan for F4C-001 or, if the
   state is already decision-complete, implement only the smallest F4C-001
   slice.
4. Keep all tests offline and fixture/cache based.
5. Update progress/current.md and progress/history.md after the checkpoint.
```

## Phase 4C Planning Transition

- Created branch `feature/phase-4c-offline-cached-html-processor` from
  `main` after confirming `main...origin/main`.
- Preserved existing local progress handoff edits on the new branch.
- Activated `phase-4c-offline-cached-html-processing-and-load` as the current
  phase with status `approved`.
- Moved `F4C-001` from `pending` to `ready` as the first Phase 4C task.
- Kept `F4C-001` unapproved; no task is currently `approved`, `in_progress`,
  or `needs_review`.
- Kept `F4C-002` and `F4C-003` pending.
- Added `specs/features/F4C-001-offline-cached-html-processor.md` for the
  offline cached HTML processor boundary.
- Updated roadmap state and task docs for the Phase 4C transition.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- Did not implement runtime code, run live scraping, contact Basketball
  Reference, refresh cache misses, write DB data, apply migrations, delete raw
  HTML, delete database records or volumes, delete Peewee/legacy code, commit,
  push, open a PR, or implement API/frontend/OVR/ranking/similarity/ML work.

## Phase 4C F4C-001 Offline Cached HTML Processor

- Owner approved implementing `F4C-001`.
- Moved `phase-4c-offline-cached-html-processing-and-load` to `in_progress`
  and moved `F4C-001` from `ready` to `in_progress`, then to `needs_review`
  after validation.
- Added `src/nba_data/scraping/offline_processor.py`.
- Added `tests/unit/test_offline_processor.py`.
- The processor accepts URL sources resolved through `HtmlCache.path_for_url`
  and explicit `.html.gz` paths under the configured cache root.
- Explicit URL sources must be Basketball Reference team-season pages matching
  `/teams/{TEAM}/{YEAR}.html`.
- Explicit path sources must include team abbreviation and season end year
  metadata, resolve under the cache root, and end in `.html.gz`.
- The processor reads cached gzip content once for each source, then calls
  `parse_team_season_page`, `normalize_team_season_page`, and
  `validate_normalized_team_season_rows`.
- Successful entries return validated normalized rows plus source context.
- Cache misses, invalid paths, read errors, and validation failures return
  per-input failures without refreshing cache misses or blocking later inputs.
- Default execution is sequential with `max_workers=1`; bounded local workers
  preserve input order for already-cached local work.
- Ran `uv run pytest tests/unit/test_offline_processor.py`: passed, 9 passed.
- Ran `uv run ruff check src/nba_data/scraping/offline_processor.py tests/unit/test_offline_processor.py`:
  passed.
- Ran `python -m json.tool tasks/feature-list.json`: passed.
- Ran `uv run ruff check .`: passed.
- Ran `uv run pytest`: passed, 96 passed, 1 skipped, and 6 Peewee deprecation
  warnings after rerunning with a longer timeout.
- Ran `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  96 passed, 1 skipped, and 6 Peewee deprecation warnings.
- Did not run live scraping, contact Basketball Reference, refresh cache
  misses, write DB data, apply migrations, delete raw HTML, delete database
  records or volumes, delete Peewee/legacy code, create a branch, commit, push,
  open a PR, or implement API/frontend/OVR/ranking/similarity/ML work.

## Phase 4C F4C-001 Continuation Handoff

- Current branch: `feature/phase-4c-offline-cached-html-processor`.
- `F4C-001` is `needs_review`.
- `phase-4c-offline-cached-html-processing-and-load` remains `in_progress`.
- `F4C-002` and `F4C-003` remain `pending`.
- Next safe action: review `F4C-001` and either close it as `done` after
  approval or move it to `changes_requested` with the smallest corrective fix.
- Do not start `F4C-002` or connect database loaders until the owner explicitly
  approves the next task.

Suggested continuation prompt:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Branch: feature/phase-4c-offline-cached-html-processor

Follow the repo startup protocol first:
1. Read AGENTS.md.
2. Run C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh.
3. Read docs/ai/WORKFLOW_PROTOCOL.md.
4. Read docs/roadmap/PHASE_GOVERNANCE.md.
5. Read docs/roadmap/CURRENT_PHASE.md.
6. Read tasks/feature-list.json.
7. Read specs/phases/phase-4c-offline-cached-html-processing-and-load.md.
8. Read specs/features/F4C-001-offline-cached-html-processor.md.
9. Read progress/current.md, progress/history.md, and progress/review.md.
10. Run git status --short --branch.

Context:
- Phase 4 SQLAlchemy migration is closed and merged via PR #6.
- Phase 4C is current:
  current_phase_id = phase-4c-offline-cached-html-processing-and-load
  current_phase_status = in_progress
- F4C-001 has been implemented and is now needs_review.
- F4C-002 and F4C-003 remain pending.
- The F4C-001 implementation added:
  - src/nba_data/scraping/offline_processor.py
  - tests/unit/test_offline_processor.py
- The processor reads only existing .html.gz cache files, then parses,
  normalizes, and validates team-season rows.
- It accepts URL sources resolved through HtmlCache.path_for_url and explicit
  .html.gz paths under the cache root.
- It does not accept BasketballReferenceClient, requests, httpx, or any generic
  network client.
- It does not write database rows or call loaders.
- Cache misses, invalid paths, read errors, and validation failures are
  per-input failures and do not refresh the cache.
- Latest validation passed:
  - python -m json.tool tasks/feature-list.json
  - uv run pytest tests/unit/test_offline_processor.py: 9 passed
  - uv run ruff check .
  - uv run pytest: 96 passed, 1 skipped, 6 Peewee deprecation warnings
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed

Guardrails:
- No live scraping.
- Do not contact Basketball Reference.
- Do not refresh cache misses.
- Do not write DB loader data from cached HTML in F4C-001.
- Do not start F4C-002 or connect database loaders.
- Do not delete raw HTML, database records, volumes, Peewee, or legacy code.
- No destructive migrations.
- No API/frontend/OVR/ranking/similarity/ML.
- Do not create another branch, commit, push, or open a PR without explicit
  owner approval.

Task:
1. Review the F4C-001 diff against its feature spec and acceptance criteria.
2. If it is correct, update progress/review.md, mark F4C-001 done, and update
   progress/current.md, progress/history.md, docs/roadmap/TASKS.md, and
   tasks/feature-list.json.
3. If you find an issue, mark F4C-001 changes_requested and implement only the
   smallest corrective fix.
4. Run offline validation after review or fixes.
5. Do not start F4C-002 unless I explicitly approve it in that session.
```
