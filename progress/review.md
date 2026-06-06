# Review Notes

## Phase 1 Review

Status: approved

Phase 1 foundations are approved for closure. The previous tracking blocker was
resolved by narrowing `.gitignore`, adding the required repo memory files to
Git, and strengthening the harness so required files must be present, unignored,
and tracked.

## Resolved Findings

- Required Phase 1 docs, specs, task/progress memory, harness scripts, and
  Codex prompts are no longer ignored by Git.
- `README.md` is included as a tracked Phase 1 file.
- `scripts/harness/init.sh` now checks required file existence, ignore status,
  and tracking status when running inside a Git worktree.
- `scripts/harness/validate.sh` now runs init checks before Ruff and Pytest.

## Automated Checks

- `.\.local\start-dev.ps1`: passed; no live scraping was run.
- `uv run ruff check .`: passed.
- `uv run pytest`: 13 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Notes

- No live scraping was run.
- No request to Basketball Reference was made.
- No commit or push was performed.
- `bash` in the default PowerShell PATH may point to the Windows WSL launcher;
  Git Bash is installed at `C:\Program Files\Git\bin\bash.exe` and can run the
  harness scripts.

## Phase 2 F2-001 Review

Status: approved

`F2-001` is approved for closure. The cache-first team-season helper is
additive, keeps legacy scraper code untouched, and is covered by offline tests
using fakes and local fixtures.

## Phase 2 F2-001 Checks

- `.\.local\start-dev.ps1`: passed; no live scraping was run.
- `uv run ruff check .`: passed.
- `uv run pytest`: 18 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Phase 2 F2-002 Review

Status: approved

`F2-002` is approved for closure. The cached parser helper reads only through
`HtmlCache`, raises `FileNotFoundError` on cache miss, and passes the cached
HTML string to the pure parser without accepting a client or touching the
database.

## Phase 2 F2-002 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 21 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Phase 2 F2-003 Review

Status: approved

`F2-003` is approved for closure. The realistic team-season fixture is compact,
local, and hand-authored rather than a raw downloaded dump. It covers visible
roster parsing, commented wrapped `totals_stats` and `advanced` tables, multiple
player rows, and repeated `tbody` header rows. Parser and cached-flow tests stay
offline and do not contact Basketball Reference.

## Phase 2 F2-003 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 23 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Phase 2 F2-004 Review

Status: approved

`F2-004` is approved for closure. The implementation adds an injectable cached
team-season HTML provider backed by the central `HtmlCache` and
`BasketballReferenceClient` path, wires it through `PlayerOperations` into the
legacy roster, totals, and advanced scrapers, and preserves legacy
loader-facing keys such as `Player`, `G`, `PTS`, and `PER`. `scrape_main.py`
was intentionally left unchanged to avoid activating live scraping or DB writes
as part of this review task.

## Phase 2 F2-004 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.
- No live scraping was run and no request to Basketball Reference was made.

## Phase 2 F2-LIVE-001 Review

Status: approved

`F2-LIVE-001` is approved for closure. The smoke test used the owner-approved URL
`https://www.basketball-reference.com/teams/BOS/2024.html`, routed through
`BasketballReferenceClient`, stored the HTML in `HtmlCache`, and verified that
the adapted legacy roster, totals, and advanced scrapers can read the fetched
or cached HTML. The task meets all acceptance criteria and is marked `done`.

## Phase 2 F2-LIVE-001 Result

- Cache result: miss before execution.
- Live requests: 1.
- HTTP status: 200.
- HTML chars: 928025.
- Cache path:
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`.
- Cache exists after: `True`.
- Parsed tables: `['advanced', 'roster', 'totals']`.
- Legacy roster rows: 19.
- Legacy totals rows: 19.
- Legacy advanced rows: 19.

## Phase 2 F2-LIVE-001 Checks

- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  29 passed, 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed.
- No DB writes, DB migrations, historical scraping, concurrency, extra URLs,
  Peewee/legacy deletion, API/frontend/OVR work, or retry after 429 occurred.

## Phase 2 F2-005 Review

Status: approved

`F2-005` is approved for closure. The loader strategy is documented in
`docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`, describes natural keys and
rerun behavior for future idempotent loaders, and stays within Phase 2 by not
implementing loaders, writing production data, or applying database migrations.

## Phase 2 F2-005 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- No live scraping was run, no request to Basketball Reference was made, no DB
  write occurred, and no database migration was applied.

## Phase 2 F2-006 Review

Status: approved

`F2-006` is approved for closure. The core migration plan is documented in
`docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`, addresses
SQLAlchemy/Peewee coexistence, and keeps Phase 2 as planning-only by avoiding
new Alembic migrations, DB writes, and legacy/Peewee deletion.

## Phase 2 F2-006 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- No live scraping was run, no request to Basketball Reference was made, no DB
  write occurred, and no database migration was applied.

## Phase 2 Cleanup Audit Review

Status: approved

The cleanup checkpoint was completed as a conservative audit only. Legacy
folders and dependencies still have active references or are explicitly retained
for coexistence, so no folders or dependencies were removed. `tenacity` has no
active imports outside lock/data, but it was left untouched because dependency
removal was out of scope and `uv.lock` must not be edited manually.

## Phase 2 Closure Review

Status: approved

Phase 2 is approved for closure. `F2-001`, `F2-002`, `F2-003`, `F2-004`,
`F2-LIVE-001`, `F2-005`, and `F2-006` are done. The phase remains the current
phase with status `done`; Phase 3 is not active and all F3 tasks remain
`pending`.

## Phase 3 Review

Status: approved

Phase 3 is approved for closure. `F3-001`, `F3-002`, and `F3-003` are done.
The parser, normalizer, and validator are separated, fixture-tested, and
offline-only.

## Phase 3 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.

## Phase 3 Notes

- Supported parser tables: roster, totals, per-game, per-minute,
  per-possession, advanced, shooting, adjusted shooting, and play-by-play.
- Normalized player rows preserve `basketball_reference_player_id` when
  available and leave missing IDs as explicit validation debt.
- `TOT` is handled as a player-season aggregate, not a real team.
- No live scraping, Basketball Reference contact, DB writes, DB migrations,
  legacy/Peewee deletion, branch/PR/commit/push, or API/frontend/OVR work
  occurred.

## Phase 4A F4A-000 Review

Status: approved

`F4A-000` is approved for closure. The feature spec and ADRs define the needed
validation strategy before legacy scraper consolidation starts: offline parity
from frozen or fixture-copied cached HTML, legacy roster/totals/advanced
comparison, golden fixture allowance, and a separate manual one-page acquisition
smoke test.

## Phase 4A F4A-000 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.

## Phase 4A F4A-000 Notes

- Manual live smoke tests must use `BasketballReferenceClient` and `HtmlCache`.
- Smoke-test defaults remain one approved URL, at most one live request on
  cache miss, 10 requests/minute default, and 20 requests/minute maximum.
- HTTP 429 stops safely through the central client behavior.
- Unit tests and CI remain fully offline.
- Bounded concurrency is allowed only for already-cached local HTML in future
  approved tasks.
- No live scraping, Basketball Reference contact, controlled backfill, DB
  writes, DB migrations, legacy/Peewee deletion, Phase 4 activation,
  API/frontend/OVR work, commit, push, or PR occurred.

## Phase 4A F4A-002 Review

Status: approved

`F4A-002` is approved for closure. The missing feature spec now exists and
documents a bounded offline-only path from cached `.html.gz` files through
parser, normalizer, validator, and a future Phase 4 idempotent loader boundary.
The design explicitly rejects network clients, cache refreshes, live scraping,
runtime processor implementation, DB writes, migrations, and API/frontend/OVR
work.

## Phase 4A F4A-002 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.

## Phase 4A F4A-002 Notes

- Default offline processing is sequential with `max_workers=1`.
- Thread, process, and async execution are allowed only as bounded local work
  over already-cached HTML.
- Future cache misses must fail instead of making live requests.
- Phase 4 SQLAlchemy migration remains inactive.
- No live scraping, Basketball Reference contact, controlled backfill, DB
  writes, DB migrations, legacy/Peewee deletion, runtime processor,
  API/frontend/OVR work, commit, push, or PR occurred.

## Phase 4A F4A-001 Review

Status: approved

`F4A-001` is approved for closure. The implementation adds a generic
cache-first Basketball Reference page provider, keeps the existing team-season
provider compatibility, and consolidates legacy player and included team
scrapers so normal operation no longer depends on direct `httpx.AsyncClient`
or `requests.get` calls.

## Phase 4A F4A-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 55 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.

## Phase 4A F4A-001 Notes

- Player roster, totals, and advanced scrapers share one
  `LegacyTeamSeasonTableAdapter` from `PlayerOperations`.
- One team-season provider read can feed roster, totals, and advanced rows for
  the same team/year while preserving loader-facing legacy keys.
- Included team scrapers use the generic page provider for `/teams/` and
  `_games.html` URLs.
- Consolidated legacy paths no longer contain per-scraper manual sleeps or
  live async fan-out.
- No live scraping, Basketball Reference contact, controlled backfill, DB
  writes, DB migrations, legacy/Peewee deletion, API/frontend/OVR work, commit,
  push, or PR occurred.

## Phase 4B F4B-001 Review

Status: approved

`F4B-001` is approved for closure. The feature spec documents the controlled raw
HTML backfill manifest as a design-only contract and does not introduce a
runtime runner, live request path, database write, migration, parser/load
execution, API/frontend/OVR work, or historical full scrape.

## Phase 4B F4B-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 55 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.

## Phase 4B F4B-001 Notes

- Manifest flow is documented as
  `approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`.
- Initial pilot default is at most five `team_season` URLs matching
  `/teams/{TEAM}/{YEAR}.html`.
- Live acquisition remains sequential, cache-first, 10 requests/minute by
  default, and never above 20 requests/minute.
- Any live request requires exact owner approval for the manifest.
- Player-specific pages remain future scope unless a later task and exact
  manifest explicitly approve them.
- `F4B-002`, `F4B-003`, `F4B-LIVE-001`, Phase 4 SQLAlchemy tasks, and Phase 4C
  tasks remain pending.

## Phase 4B F4B-002 Review

Status: approved

`F4B-002` is approved for closure. The implementation validates approved
`team_season` raw HTML backfill manifests, reports expected cache paths,
cache hit/miss state, and estimated live request count, and exposes an offline
`nba-data backfill dry-run <manifest.json>` command.

## Phase 4B F4B-002 Checks

- `uv run pytest tests/unit/test_backfill_manifest.py`: passed, 8 passed
  before closure.
- `uv run ruff check src/nba_data/scraping/backfill_manifest.py src/nba_data/cli/main.py tests/unit/test_backfill_manifest.py`:
  passed before closure.

## Phase 4B F4B-002 Notes

- Dry-run validation does not accept a network client.
- Cache misses are counted as estimated future live requests only.
- No live scraping, Basketball Reference contact, raw HTML writes outside
  temporary test cache, DB writes, migrations, runner execution, API/frontend,
  or OVR work occurred.

## Phase 4B F4B-003 Review

Status: approved

`F4B-003` is approved for closure. The acquisition runner consumes approved
manifests, checks `HtmlCache` before each client call, records cache hits
without network calls, fetches misses sequentially through a
`BasketballReferenceClient`-compatible client, writes fetched HTML through
`HtmlCache`, and stops with a partial report on client failure.

## Phase 4B F4B-003 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.

## Phase 4B F4B-003 Notes

- The CLI acquisition command still requires
  `--execute-approved-manifest`.
- Unit tests use fakes and temporary caches only.
- `F4B-LIVE-001` is moved to `ready`, not `approved`.
- No live scraping, Basketball Reference contact, live pilot, DB writes,
  migrations, raw HTML deletion, legacy/Peewee deletion, API/frontend/OVR work,
  branch creation, push, or PR occurred.

## Phase 4B F4B-LIVE-001 Review

Status: approved

`F4B-LIVE-001` is approved for closure. The owner-approved two-URL manifest
stayed within Phase 4B acquisition-only scope: BOS 2024 was served from cache,
DEN 2023 was fetched once through the controlled runner, and the fetched HTML
was stored as `.html.gz` through `HtmlCache`.

## Phase 4B F4B-LIVE-001 Result

- Manifest:
  `tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`.
- Approved URLs:
  `https://www.basketball-reference.com/teams/BOS/2024.html` and
  `https://www.basketball-reference.com/teams/DEN/2023.html`.
- Pre-run dry-run: 2 entries, 1 cache hit, 1 cache miss, 1 estimated live
  request.
- Acquisition: 2 processed entries, 1 cache hit, 1 fetched page, 0 failures,
  and `live_request_count=1`.
- DEN 2023 cache path:
  `data\raw\html\basketball-reference\teams-den-2023.html-4bfff60cb079ffe5.html.gz`.
- DEN 2023 gzip inspection: 139188 bytes compressed, 911464 HTML characters,
  expected Denver/roster/totals/advanced markers present, wrong-team Boston
  marker absent.
- Post-run dry-run: 2 cache hits, 0 cache misses, 0 estimated live requests.

## Phase 4B F4B-LIVE-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `python -m json.tool tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`:
  passed.
- `uv run nba-data backfill dry-run tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`:
  passed with 2 cache hits and 0 estimated live requests.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.

No rerun live acquisition, extra Basketball Reference contact, DB writes,
migrations, parser/load offline processing, full historical scraping,
concurrency, raw HTML deletion, legacy/Peewee deletion, API/frontend/OVR work,
branch creation, commit, push, or PR occurred during review closure.

## Phase 4B Closure Review

Status: approved

Phase 4B is approved for closure. The phase has a reviewed manifest strategy,
offline dry-run validation, sequential cache-first acquisition runner, and a
recorded owner-approved two-URL pilot. Phase 4 is now current as
`phase-4-sqlalchemy-migration` with status `proposed`, and `F4-001` is `ready`
but not approved.

## Phase 4B Closure Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- `uv run alembic check`: failed with existing nullable drift on
  `raw.raw_pages.fetched_at`, `raw.scraper_requests.requested_at`, and
  `raw.scraper_runs.started_at`.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.

No live acquisition was rerun, no extra Basketball Reference contact occurred,
and no DB writes, migrations, parser/load offline processing, raw HTML
deletion, legacy/Peewee deletion, API/frontend/OVR work, branch creation,
commit, push, or PR occurred during the transition.

## Phase 4 F4-001 Review

Status: approved

`F4-001` is approved for closure. The additive core migration adds reviewed
SQLAlchemy models and Alembic revision `0002_core_team_player_season.py` for
team-season, player-season, and player-team-season relationships while
preserving Peewee and legacy coexistence.

## Phase 4 F4-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 77 passed and 6 Peewee deprecation warnings.
- `uv run alembic upgrade head`: passed.
- `uv run alembic check`: initially failed only with the pre-existing raw
  nullable drift, which was deferred to `F4-003`.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  77 passed and 6 Peewee deprecation warnings.

No live scraping, Basketball Reference contact, loader implementation,
destructive migration, data deletion, Peewee/legacy deletion, API/frontend/OVR
work, branch creation, commit, push, or PR occurred.

## Phase 4 F4-003 Review

Status: approved

`F4-003` is approved for closure. The local database validation path is
repeatable, runs PostgreSQL-backed Alembic upgrade/check validation, and aligns
the raw timestamp SQLAlchemy metadata with the existing nullable
`0001_initial_raw_core` migration.

## Phase 4 F4-003 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 78 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  78 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`: passed;
  `alembic check` reported no new upgrade operations.
- `uv run alembic current`: reported `0002_core_team_player_season (head)`.
- `git diff --cached --name-only -- .env data/raw`: passed with no output.

No live scraping, Basketball Reference contact, loader implementation, Phase
4C work, destructive migration, data deletion, Peewee/legacy deletion,
API/frontend/OVR/ranking/similarity/ML work, branch creation, commit, push, or
PR occurred.

## Phase 4 F4-002 Review

Status: approved

`F4-002` is approved for closure. The implementation adds portable SQLAlchemy
core repositories and a team-season core loader that validates normalized input
before writing, reruns idempotently, leaves transactions uncommitted, and keeps
`TOT` as an aggregate rather than a real team.

## Phase 4 F4-002 Review Findings

- `load_team_season_core(...)` validates normalized rows and duplicate natural
  keys before repository writes.
- Repositories use SQLAlchemy `select(...)` plus `add/flush`, without
  dialect-specific upserts.
- Loader and repository methods do not call `session.commit()`.
- Caller rollback behavior is covered; the PostgreSQL smoke test runs inside a
  transaction that is rolled back.
- Existing meaningful team and player names are not overwritten by fallback or
  empty values.
- `player_name` is descriptive only; identity uses
  `basketball_reference_player_id`.
- `TOT` is blocked as a real team, alias, and team-season. Aggregate rows
  create player-season identity records without creating `TOT` team,
  team-season, or player-team-season records.
- No new Alembic revision was added for `F4-002`; the only Phase 4 core schema
  revision is `0002_core_team_player_season.py` from `F4-001`.

## Phase 4 F4-002 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 88 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  88 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/db-validate.sh`: passed;
  `alembic check` reported no new upgrade operations and the PostgreSQL smoke
  test passed.
- `uv run alembic current`: reported `0002_core_team_player_season (head)`.
- `git diff --cached --name-only -- .env data/raw`: passed with no output.

No live scraping, Basketball Reference contact, Phase 4C processing, stats
loading, destructive migration, data deletion, Peewee/legacy deletion,
API/frontend/OVR/ranking/similarity/ML work, branch creation, commit, push, or
PR occurred.

## Phase 4 Closure Review

Status: approved

Phase 4 is approved for closure. `F4-001`, `F4-002`, and `F4-003` are done.
The phase leaves behind additive SQLAlchemy core schema, idempotent loader
repositories for validated normalized rows, and a repeatable PostgreSQL
validation path. Phase 4C remains pending until explicit owner approval.

## Phase 4C F4C-001 Review

Status: approved

`F4C-001` is approved for closure. The offline processor reads already-cached
`.html.gz` team-season inputs, runs cached gzip read -> parse -> normalize ->
validate, and returns validated normalized rows or actionable per-input
failures without accepting a network client or writing database rows.

## Phase 4C F4C-001 Review Findings

- URL sources are restricted to explicit Basketball Reference team-season pages
  and resolve through `HtmlCache.path_for_url`.
- Explicit path sources require team abbreviation and season year metadata,
  must end in `.html.gz`, and must resolve under the configured cache root.
- Cache misses, invalid paths, read errors, and validation failures are
  reported per input without refreshing the cache or blocking later inputs.
- Default execution is sequential with `max_workers=1`; bounded local workers
  preserve input order for already-cached local work.
- The processor does not accept or import `BasketballReferenceClient`,
  `requests`, `httpx`, or a generic network client.
- No database sessions, SQLAlchemy loader calls, migrations, raw HTML deletion,
  API/frontend, generated metrics, OVR, ranking, similarity, ML work, or
  `F4C-002` loader connection were introduced.

## Phase 4C F4C-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run pytest tests/unit/test_offline_processor.py`: passed, 9 passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 96 passed, 1 skipped, and 6 Peewee deprecation
  warnings after rerunning with a longer timeout.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  96 passed, 1 skipped, and 6 Peewee deprecation warnings.

No live scraping, Basketball Reference contact, cache refresh, DB writes,
loader integration, destructive migration, data deletion, Peewee/legacy
deletion, API/frontend/OVR/ranking/similarity/ML work, branch creation, commit,
push, or PR occurred during review closure.

## Phase 4C F4C-002 Review

Status: approved

`F4C-002` is approved for closure. The offline loader bridge starts from
validated offline processor report entries, converts only validated entries to
`TeamSeasonLoadBatch`, loads through the existing idempotent
`load_team_season_core(...)` path, and preserves caller-owned transaction
boundaries.

## Phase 4C F4C-002 Review Findings

- Loading starts from `OfflineTeamSeasonProcessingReport` entries, not raw
  HTML.
- Processor failure entries are skipped and do not call DB loaders.
- Each validated entry runs inside `session.begin_nested()`, so loader
  exceptions roll back partial writes for that entry.
- Loader orchestration does not call `session.commit()`.
- Idempotent reruns do not create duplicate core rows.
- Source lineage stays at result/report level only:
  `source_url`, `cache_path`, `team_abbreviation`, and `season_year`.
- No network client, `BasketballReferenceClient`, `requests`, or `httpx`
  boundary was added to the offline loader.
- No migrations, DB tables, source lineage columns, F4C-003
  reporting/quarantine workflow, full historical load, API/frontend/OVR,
  ranking, similarity, or ML work was introduced.

## Phase 4C F4C-002 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 102 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  102 passed, 1 skipped, and 6 Peewee deprecation warnings.

No live scraping, Basketball Reference contact, cache refresh, destructive
migration, data deletion, Peewee/legacy deletion, branch creation, commit,
push, PR, or `F4C-003` work occurred during review closure.

## Phase 4C F4C-003 Review

Status: approved

`F4C-003` is approved for closure. The implementation adds report-level
audit/quarantine behavior over existing offline processing and load reports,
without adding live acquisition, cache refresh, migrations, DB tables, lineage
columns, API/frontend/OVR work, or a full historical load.

## Phase 4C F4C-003 Review Findings

- The audit report starts from `OfflineTeamSeasonProcessingReport` plus an
  optional `OfflineTeamSeasonLoadReport`; it does not read raw HTML or accept a
  network client.
- Reports distinguish parsed, validated, loaded, skipped, and quarantined row
  counts.
- Validation failures preserve invalid normalized rows as quarantined rows while
  keeping them out of `validated_rows` and loader input.
- Loader failures quarantine only the validated rows for the failed entry.
- Quarantine entries retain source URL, cache path, team abbreviation, season
  year, validation issue details where available, error messages, and retry
  hints.
- Retry safety is covered by rerunning the same validated report through the
  idempotent loader path without duplicate load effects.
- No `BasketballReferenceClient`, `requests`, `httpx`, cache refresh, new
  Peewee code, migrations, DB tables, lineage columns, API/frontend/OVR,
  ranking, similarity, or ML work was introduced.

## Phase 4C F4C-003 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 106 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Phase 4C Closure Review

Status: approved

Phase 4C is approved for closure. `F4C-001`, `F4C-002`, and `F4C-003` are
done. The phase leaves behind the offline cached HTML processor, idempotent
loader bridge, and audit/quarantine reporting workflow needed before any future
broader pilot or Phase 5 transition.

No live scraping, Basketball Reference contact, cache refresh, destructive
migration, data deletion, Peewee/legacy deletion, branch creation, commit,
push, PR, API/frontend/OVR/ranking/similarity/ML work, or Phase 5 activation
occurred during closure.

## Phase 4D Planning Transition Review Notes

Status: planning prepared

Phase 4D has been introduced as a planning-only transition before any API phase.
No Phase 4D implementation task is in progress or needs review. `F4D-001` is
ready for future owner approval, while `F4D-002`, `F4D-003`, and `F4D-004`
remain pending.

The review focus for the next implementation checkpoint should be that Phase 4D
stays offline-only: existing cached `.html.gz` files only, no live scraping, no
cache refresh, no Basketball Reference contact, no data deletion, no
destructive migrations, and no API/frontend/OVR/ranking/similarity/
recommendations/ML work.

## Phase 4D-A Planning Transition Review Notes

Status: planning prepared

Phase 4D-A has been introduced as a controlled acquisition subphase inside
Phase 4D. `F4D-ACQ-001` is ready for future owner approval; all live
acquisition and database preparation tasks remain pending.

Review focus for the next checkpoint should confirm that manifest generation is
NBA-only, team-season-only, and covers exactly 775 unique
`/teams/{TEAM}/{YEAR}.html` URLs for Basketball Reference season end years 2000
through 2025. Live acquisition remains gated behind explicit owner approval and
an execution flag.

## Phase 4D-A F4D-ACQ-001 Review

Status: approved

`F4D-ACQ-001` is approved for closure. The implementation adds deterministic
NBA team-season manifest generation and an offline dry-run report for
Basketball Reference season end years 2000 through 2025, without accepting a
network client or introducing live acquisition.

## Phase 4D-A F4D-ACQ-001 Review Findings

- The manifest contains exactly 775 unique URLs and every URL matches
  `/teams/{TEAM}/{YEAR}.html`.
- The catalog covers the approved NBA team and franchise-lineage boundaries for
  season end years 2000 through 2025.
- The dry-run uses `HtmlCache.path_for_url(...)` to report cache hits, missing
  cache entries, skipped entries, unsupported entries, and estimated fetch
  count.
- No manifest JSON artifact was committed.
- The manifest module does not import or accept `BasketballReferenceClient`,
  `requests`, `httpx`, parser, loader, or database boundaries.
- No live scraping, Basketball Reference contact, raw HTML writes, database
  writes, parser/load/backfill execution, API/frontend/OVR/ranking/similarity/
  ML work, branch creation, commit, push, or PR occurred during review closure.

## Phase 4D-A F4D-ACQ-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run pytest tests/unit/test_nba_team_season_manifest.py`: passed, 7
  passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 113 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 113
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Phase 4D-A F4D-ACQ-LIVE-001 Review Prep

Status: needs_review

`F4D-ACQ-LIVE-001` is ready for review as an offline implementation checkpoint.
The command exists but was not executed live. Review should confirm that live
execution remains separately gated after approval and that no Basketball
Reference contact occurred during implementation.

## Phase 4D-A F4D-ACQ-LIVE-001 Review Focus

- The command requires `--owner-approved` and `--execute-approved-manifest`.
- The live command requires explicit `START_YEAR END_YEAR` arguments.
- Valid live ranges may be any inclusive subset inside 2000-2025.
- Invalid live ranges fail before client creation.
- Manifest ID `nba-team-season-2000-2025` and the 775-entry count are verified
  before the live client is created, then the manifest is filtered to the
  requested range.
- Production acquisition uses only `BasketballReferenceClient`.
- Cache hits do not call the client and do not overwrite existing `.html.gz`
  files.
- Fetched content must be non-empty and HTML-shaped before storage; no table
  parsing occurs.
- Cache writes use a temporary gzip file and verification before replacing the
  final cache file.
- Partial reports include `stopped_reason`, `stopped_at_entry`, and per-entry
  index/team/season/URL/cache/status/error details.
- `--output` writes the same JSON report that is printed to stdout.

## Phase 4D-A F4D-ACQ-LIVE-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run pytest tests/unit/test_nba_team_season_acquisition.py`: passed, 12
  passed.
- `uv run pytest tests/unit/test_nba_team_season_acquisition.py`: passed, 19
  passed after the safe gzip write regression fix.
- `uv run pytest tests/unit/test_nba_team_season_acquisition.py
  tests/unit/test_nba_team_season_manifest.py`: passed, 25 passed after the
  flexible-year refinement.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 131 passed, 1 skipped, and 6 Peewee deprecation
  warnings after the flexible-year refinement.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 131
  passed, 1 skipped, and 6 Peewee deprecation warnings.
- `python -m json.tool tasks/feature-list.json`: passed after the
  owner-approved acquisition and progress updates.
- `uv run ruff check .`: passed after the owner-approved acquisition and
  progress updates.
- `uv run pytest`: passed, 132 passed, 1 skipped, and 6 Peewee deprecation
  warnings after the owner-approved acquisition and progress updates.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 132
  passed, 1 skipped, and 6 Peewee deprecation warnings after the
  owner-approved acquisition and progress updates.

No live acquisition, Basketball Reference contact, database writes,
parser/load/backfill execution, API/frontend/OVR/ranking/similarity/ML work,
branch creation, commit, push, or PR occurred during implementation.

## Phase 4D-A F4D-ACQ-LIVE-001 Acquisition Result

Status: needs_review

The owner-approved 2000-2025 live acquisition completed and is ready for review
against the acquisition report.

- Report path: `reports/acquisition-2000-2025-20260530.json`.
- Total URLs: 775.
- Processed entries: 775.
- Cache hits: 2.
- Fetched entries: 773.
- Failed entries: 0.
- Rate-limited entries: 0.
- Completed: true.
- Post-run dry-run: 775 cache hits, 0 missing cache entries, 0 estimated
  fetches.
- Final cache count: 775 team-season `.html.gz` files.
- Session total live requests: 774, including the one initial ATL 2000 request
  that stopped before final cache write due to the safe-write newline
  verification issue.
- Final validation passed after this acquisition result was recorded.

Review should confirm that no DB writes, parser/load/backfill execution, extra
page types, data deletion, destructive migrations, API/frontend/OVR work,
branch creation, commit, push, or PR occurred.

## Phase 4D-A F4D-ACQ-LIVE-001 Review Closure

Status: approved

`F4D-ACQ-LIVE-001` is approved for closure. The implementation and the
owner-approved 2000-2025 acquisition report satisfy the task acceptance
criteria, and the task is marked `done`.

## Phase 4D-A F4D-ACQ-LIVE-001 Review Findings

- The command keeps the approved CLI contract:
  `nba-data acquisition acquire-nba-team-seasons START_YEAR END_YEAR
  --owner-approved --execute-approved-manifest [--output PATH]`.
- The saved report contains 775 entries, 2 cache hits, 773 fetched entries, 0
  skipped entries, 0 failures, 0 rate-limited entries, and `completed=true`.
- Report entries use only approved `/teams/{TEAM}/{YEAR}.html` URLs; no bad or
  duplicate URLs were found, and every reported cache path exists locally.
- Cache artifacts under `data/raw/html/basketball-reference` total 775
  `.html.gz` files and 0 `.tmp` files.
- The prior stopped attempts are preserved in progress: one process-launch
  quoting failure before execution and one safe-write verification stop after
  the ATL 2000 request, before final cache write.
- No DB writes, parser/load/backfill execution, extra page types, data
  deletion, destructive migrations, API/frontend/OVR/ranking/similarity/ML
  work, branch creation, commit, push, or PR occurred during review closure.

## Phase 4D-A F4D-ACQ-LIVE-001 Closure Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 132 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  132 passed, 1 skipped, and 6 Peewee deprecation warnings.

## Phase 4D F4D-001 Review Prep

Status: needs_review

`F4D-001` is ready for review. The implementation adds an offline cached HTML
inventory utility and unit tests without adding a CLI command, network client,
parser, loader, database session, migration, or backfill execution.

## Phase 4D F4D-001 Review Focus

- `build_cached_html_inventory(cache=HtmlCache(...))` discovers only existing
  `.html.gz` files under the configured cache root.
- Resolved file paths are checked against the cache root before any gzip read.
- Basketball Reference team-season metadata is inferred from existing
  `HtmlCache` filename conventions and reported as `source_url`,
  `team_abbreviation`, `season_year`, `season_end_year`, and `page_type`.
- Valid candidates are limited to the reviewed 2000-2025 NBA team-season
  manifest.
- Duplicate, missing-metadata, unsupported-path, and invalid/unreadable entries
  are separately counted and preserved in the report.
- Unit tests use only temporary local cache fixtures.
- Real local cache inspection found 775 valid candidates and no inventory
  anomalies.

## Phase 4D F4D-001 Checks

- `uv run pytest tests/unit/test_cache_inventory.py`: passed, 8 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 141 passed, 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  141 passed and 6 Peewee deprecation warnings.

No live scraping, Basketball Reference contact, cache refresh, parser/load/
backfill execution, database write, data deletion, destructive migration,
API/frontend/OVR/ranking/similarity/recommendations/ML work, branch creation,
commit, push, or PR occurred during implementation.

## Phase 4D F4D-001 Review Closure

Status: approved

The owner approved `F4D-001` and it is marked `done`. The cached HTML inventory
utility and tests are accepted as the safe input boundary for `F4D-002`.

## Phase 4D F4D-002 Review Prep

Status: needs_review

`F4D-002` is ready for review. The implementation adds the full offline
backfill utility and guarded CLI command without scraping, contacting
Basketball Reference, refreshing cache, deleting data, running migrations, or
introducing API/frontend/OVR/ranking/similarity/recommendations/ML work.

## Phase 4D F4D-002 Review Focus

- `run_full_offline_backfill(...)` builds the F4D-001 inventory and selects
  only entries with `status == "valid"`.
- Valid inventory entries become explicit-path `OfflineTeamSeasonSource`
  inputs, preserving the reviewed cache artifact path for processing.
- Processing runs through `process_offline_team_season_sources(...)`.
- Loading runs through `load_offline_team_season_report(...)`, preserving the
  existing entry-level nested transaction behavior.
- Reporting runs through `build_offline_team_season_audit_report(...)`.
- `run_full_offline_backfill(...)` does not call `commit()` or `rollback()`;
  the CLI owns the outer transaction.
- `nba-data backfill offline` refuses to write unless
  `--execute-approved-backfill` is supplied.
- Unit tests cover valid routing, skipped inventory statuses, idempotent rerun,
  loader rollback, caller-owned commit behavior, report serialization, CLI
  guard behavior, and no-network/no-migration boundaries.

## Phase 4D F4D-002 Checks

- `uv run pytest tests/unit/test_offline_backfill.py`: passed, 10 passed.
- `uv run pytest tests/unit/test_cache_inventory.py tests/unit/test_offline_backfill.py tests/unit/test_offline_processor.py tests/unit/test_offline_loader.py tests/unit/test_offline_reporting.py tests/unit/test_team_season_loader.py`:
  passed, 46 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- Focused Ruff on `src/nba_data/scraping/offline_backfill.py`,
  `src/nba_data/cli/main.py`, and `tests/unit/test_offline_backfill.py`:
  passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: first run timed out at 120 seconds; rerun with a longer
  timeout passed, 150 passed, 1 skipped, and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  150 passed, 1 skipped, and 6 Peewee deprecation warnings.

## Phase 4D F4D-002 Review Closure

Status: approved

`F4D-002` is approved for closure. The full offline backfill command stays
within the reviewed Phase 4D boundary: it reads only the F4D-001 local cache
inventory, selects valid entries, processes through Phase 4C offline processor
inputs, loads through existing idempotent core loaders, preserves caller-owned
transaction behavior, and produces the existing audit/quarantine report.

No live scraping, Basketball Reference contact, cache refresh, data deletion,
destructive migration, API/frontend/stats persistence/OVR/ranking/similarity/
recommendations/ML work, branch creation, commit, push, or PR occurred during
review closure.

## Phase 4D F4D-003 Review Closure

Status: approved

`F4D-003` is approved for closure. The implementation adds read-only offline
database validation over the loaded `core` schema and the saved backfill
report. It checks expected table counts, season coverage, duplicate logical
rows, orphan relationships, team-seasons without players, suspiciously low
per-season counts, `TOT` real-team misuse, missing Basketball Reference player
IDs, and nonzero backfill failure/quarantine counts.

## Phase 4D F4D-004 Review Closure

Status: approved

`F4D-004` is approved for closure. The readiness workflow is documented in
`docs/validation/OFFLINE_DATABASE_PREPARATION.md`, including local PostgreSQL
startup, Alembic migration commands, cache inventory, full offline backfill,
data quality validation, expected loaded counts, and SQL queries useful for
future read-only API exploration.

## Phase 4D Final Closure Review

Status: approved

Phase 4D is approved for closure. `F4D-002`, `F4D-003`, and `F4D-004` were
explicitly owner-approved for block closure and are marked `done`. Phase 4D is
marked `done`; `F4E-001` through `F4E-006` remain `pending`.

## Phase 4D Final Closure Checks

- `uv run pytest tests/unit/test_offline_database_validation.py`: passed, 8
  passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 159 passed and 6 Peewee deprecation warnings.
- `uv run nba-data validate offline-database --backfill-report reports/offline-backfill-2000-2025.json`:
  passed with `passed: true` and no issues.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 159
  passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed, 159
  passed and 6 Peewee deprecation warnings.

No live scraping, Basketball Reference contact, cache refresh, data deletion,
destructive migration, F4E/F5/API/frontend/stats persistence/OVR/ranking/
similarity/recommendations/ML work, branch creation, commit, push, or PR
occurred during final Phase 4D closure.

## Phase 4E F4E-001 Review Prep

Status: needs_review

`F4E-001` is ready for owner review as a documentation-only schema design
checkpoint. Phase 4E is now current and `in_progress`; `F4E-001` is
`needs_review`; `F4E-002` through `F4E-006` remain `pending`.

## Phase 4E F4E-001 Review Focus

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` documents all 17 reviewed
  `stats` tables.
- Team-stint and roster tables FK to `core.player_team_seasons.id`.
- Aggregate player-season tables FK to `core.player_seasons.id`.
- Every table has a surrogate PK, unique FK grain constraint, lineage columns,
  nullable stat columns, and reviewed SQL type recommendations.
- The design records observed normalized keys from the current parser and
  normalizer and final `normalized key -> DB column` mappings.
- `TOT` is routed only to aggregate player-season tables and is never treated
  as a real team or roster row.
- Legacy totals, advanced, and roster ideas are documented as conceptual
  references only; name-based identity, loose years, FK-to-roster identity,
  numeric `CharField`s, missing idempotency, and mixed identity/stat entities
  are rejected.
- `F4E-002` is prepared to implement `src/nba_data/db/models/stats.py`, model
  exports, and the next Alembic revision without redesigning the schema.

## Phase 4E F4E-001 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 158 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 158
  passed, 1 skipped, and 6 Peewee deprecation warnings.

No SQLAlchemy stats models, Alembic migrations, repositories, loaders, backfill
commands, database writes, live scraping, Basketball Reference contact, cache
refresh, API/frontend/OVR/ranking/similarity/recommendations/ML work, branch
creation, commit, push, or PR occurred during this checkpoint.
