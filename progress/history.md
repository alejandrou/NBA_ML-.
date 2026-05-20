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
