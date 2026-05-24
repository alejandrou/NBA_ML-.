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
