---
id: F6-013
title: Serve the regular-season aggregate and stint stat routes
track: app
areas:
  - api
  - database-read
  - testing
  - documentation
priority: 90
depends_on:
  - F6-004
  - F6-012
  - F4E-024
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - src/nba_data/db/models/stats.py
  - src/nba_data/domain/team_codes.py
  - src/nba_data/api/routers/players.py
  - src/nba_data/api/services/players.py
  - src/nba_data/api/schemas/players.py
  - src/nba_data/api/services/readiness.py
  - src/nba_data/db/repositories/queries/players.py
  - tests/unit/test_player_api.py
  - tests/unit/test_api_readiness.py
validation:
  - uv run pytest tests/unit/test_player_stats_api.py tests/unit/test_player_stats_service.py tests/unit/test_player_stats_query_repository.py tests/unit/test_api_readiness.py tests/unit/test_api_foundation.py tests/unit/test_player_api.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. The routes read the database; no load, backfill, or rebuild happens here.
---

# Goal

Serve the regular-season half of the two statistics route templates across all
eight families:

```text
GET /api/v1/players/{pid}/seasons/{season_year}/regular/aggregate/{family}
GET /api/v1/players/{pid}/seasons/{season_year}/regular/stints/{family}
```

`stats.player_season_{family}` is the aggregate grain and
`stats.player_team_season_{family}` the stint grain. The family schemas built
here are reused unchanged by F6-014.

# Evidence and current state

- `API_CONTRACT.md` fixes the routing table, the body shape, `is_multi_team`,
  the null and JSON-number rules, the stint ordering
  (`basketball_reference_team_id ASC`), and the status codes.
- All four dimensions inherit the same eight column mixins
  (`src/nba_data/db/models/stats.py`): `_TotalsColumnsMixin`,
  `_PerGameColumnsMixin`, and so on. The mixins also carry `rk`, `age`,
  `position`, `awards`, and `player_name_display`.
- **Data health is settled.** F4E-024 rehearsed the rebuild and F4E-031 applied
  it: the persistent `nba` database is at the `-v4` baseline since 2026-09-05
  (`docs/validation/OFFLINE_DATABASE_PREPARATION.md`): 101,336 regular player
  rows, 12,667 player-seasons, zero rows at `-v1` to `-v3`. The card text that
  called the aggregate family stale and 625 seasons short predates that run.
- Readiness checks one schema: `REQUIRED_SCHEMA = "core"` and bare table names
  (`src/nba_data/api/services/readiness.py:22-29`). It cannot yet name a
  `stats` table.
- `API_ARCHITECTURE.md` confines API reads to `db/repositories/queries/`;
  `StatsRepository` is the write path and is not reused.
- Pydantic serializes `Decimal` to a JSON string by default; no schema in
  `src/nba_data/api/schemas/` handles `Decimal` today.

# Human decisions or resources

- [x] **Dispatch: generated, typed routes.** One map from family to the two ORM
      models and two Pydantic bodies drives a loop that registers one route per
      family and grain, each with its own `response_model`. OpenAPI therefore
      carries a distinct, fully typed body per family, which the web app's
      generated types need (ADR 0019). A single `{family}` route would publish
      an untyped union. After the literal routes, one hidden route
      (`include_in_schema=False`) takes `{season_type}` and `{family}` as enums,
      so an unrecognized value still returns the contract's 422; a valid but
      unserved combination (postseason, until F6-014) returns 404.
- [x] **Staleness does not hide rows.** The API publishes no lineage and filters
      on none; data health is the `data` track's gate
      (`validate official-stats`). The database is at `-v4`, so the question no
      longer blocks shipping.
- [x] **Rates**: one annotated type, `ApiDecimal =
      Annotated[Decimal, PlainSerializer(float, return_type=float,
      when_used="json")]`, in a new `src/nba_data/api/schemas/common.py`, used
      by every `Numeric` column. OpenAPI shows `number`. `0.4660` serializes as
      `0.466`; JSON numbers carry no scale, so the contract's "at their stored
      scale" is corrected to "as the stored value".
- [x] **A stint without a stat row is omitted.** The collection lists stat rows
      only; membership is already served by the season index's `teams`.
      Inventing a row of nulls would assert a stint the stat table does not
      hold.
- [x] **Published columns**: every column of the family's mixin except
      `player_name_display` (a named non-promise), the primary key, the grain
      FK, and lineage. `rk`, `age`, `position`, and `awards` are published
      verbatim, `null` when absent.

# Acceptance criteria

- `src/nba_data/db/repositories/queries/player_stats.py`: read-only queries for
  one aggregate row and one page of stint rows of a family, scoped by player id
  and season year through `core.player_seasons` /
  `core.player_team_seasons`, NBA seasons only, never mutating the Session.
- `src/nba_data/api/schemas/player_stats.py`: one aggregate and one stint body
  per family. A unit test derives each body's stat fields from the mapped
  mixin columns minus the exclusions above and asserts equality, so a new
  stored column fails the test until it is published or excluded.
- `is_multi_team` comes from `team_codes.is_multi_team_marker`; a test pins
  `2TM` and `5TM` as true, a real code as false, and `null` as false.
- Routes as decided above. Status codes exactly per contract: 404
  `Player not found`, 404 `Player season not found`, 404 `Statistics not found`
  for a missing aggregate row, 200 with an empty `items` list for an empty stint
  collection, 422 for an unrecognized `{season_type}` or `{family}`, 422 for a
  non-integer `{season_year}`. `detail` strings are fixed.
- Stint collections use the envelope, `page_size` ≤ 100, ordered by team code.
- Readiness takes schema-qualified names (`core.teams`, `stats.…`) and adds the
  16 regular `stats` tables served here. `test_api_readiness.py` covers a
  missing `stats` table → 503 `Database schema not ready`.
- `TestClient` tests cover: every family on both grains; a `2TM` aggregate with
  its stints; an old season whose newer columns are `null` (not `0`, not
  omitted); a rate asserted as a JSON number; no lineage key and no
  `player_name_display` in any body; the hidden route's 422 and 404.
- `test_api_foundation.py` still passes (every OpenAPI path under `/api/v1/`;
  the hidden route is not in the document).
- `API_CONTRACT.md`: the "Specified, not yet served" marker names only the
  postseason routes; the stale F4E-024 sentence is removed; the published
  column rule, the omitted-stint rule, and the rate wording are recorded.

# Scope

`src/nba_data/api/` (routers, services, schemas),
`src/nba_data/db/repositories/queries/`, `readiness.py`, `tests/unit/`, and
`docs/architecture/API_CONTRACT.md`.

# Out of scope

Postseason routes (F6-014). The roster table. Any write, load, backfill, or
rebuild. Any schema change. Generated metrics. Contacting Basketball Reference.

# Impact

- Sixteen served combinations; readiness becomes multi-schema.

# Cross-track impact

- None.

# Implementation notes

The contract is the authority on what a body contains; `stats.py` on which
columns a family has. Do not restate the collection envelope or the error
taxonomy. Build the family map with both season types' tables named, so F6-014
only registers the postseason entries.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — as listed in the acceptance criteria.

# Review evidence

## Branch review — 2026-10-25

- Reviewed the full working-tree change, including untracked statistics modules
  and tests; the branch has no committed diff against `origin/main`.
- Finding (P2, fixed): readiness omitted `core.team_seasons`, although every
  stint query joins it. A missing table could leave readiness at 200 while
  stint requests fail. Added the dependency to readiness and the contract.
  The new missing-table test failed with 200 before the fix and passes with
  503 `Database schema not ready` afterward.
- Re-ran the six-file focused validation command listed above: 105 passed.
- `uv run pytest -m "not integration and not live"`: 1279 passed,
  251 deselected; dependency deprecation warnings only.
- `uv run ruff check .`: all checks passed.
- `uv run mypy src/nba_data`: no issues in 87 source files.
- `uv run python scripts/validate_tasks.py` and the same command with
  `--all-worktrees`: both passed.
- Additional offline Python probe populated all 450 published column values
  across the 16 family/grain response bodies, checking stored-value mapping
  and JSON numeric serialization/OpenAPI types: passed.
- No further implementation defects found. This review did not repeat the
  earlier PostgreSQL integration or persistent-database smoke runs; their
  historical evidence below is unchanged. The card remains in review for the
  owner's manual testing.

## Automated validation

- Command: `uv run pytest tests/unit/test_player_stats_api.py tests/unit/test_player_stats_service.py tests/unit/test_player_stats_query_repository.py tests/unit/test_api_readiness.py tests/unit/test_api_foundation.py tests/unit/test_player_api.py`
- Result: 104 passed.
- Command: `uv run ruff check .` — Result: All checks passed.
- Command: `uv run mypy src/nba_data` — Result: no issues found in 87 source files.
- Command: `uv run pytest -m "not integration and not live"` — Result: 1278 passed, 251 deselected.
- Command: `uv run python scripts/validate_tasks.py` — Result: Task validation passed.
- Command (beyond the card's list, because readiness SQL changed):
  `uv run python scripts/validate_postgres_local.py` with `DATABASE_URL` pointed at
  `127.0.0.1` for that process only. Result: migrations, the 0008 round trip,
  `alembic check`, and 251 integration tests passed on a temporary database,
  including `GET /health/ready` = 200 against the real `core` + `stats` catalog.
  `bash scripts/validate_database.sh` itself could not run from this worktree:
  its `docker compose up` collides with the `nba_postgres` container owned by
  the other worktree's compose project. Through `localhost` every connection on
  this machine stalls ~60 s on IPv6 before succeeding, so the lane looks hung.

## Manual happy path

1. `uv run nba-data serve` against the `nba` database (at `0009`, seasons
   2000-2026 since F8-003's load on 2026-10-24).
2. `GET /api/v1/players/jamesle01/seasons/2008/regular/aggregate/totals`.
3. `GET /api/v1/players/jamesle01/seasons/2008/regular/stints/advanced`, then a
   traded player's season (any season whose index shows two `teams`) on both grains.
4. Open `/docs`: sixteen statistics operations under "player statistics", each
   with its own family body.

Expected result: 200 bodies with identity fields first, stored column names,
rates as JSON numbers (`0.466`, not `"0.4660"`), `null` for missing stats, no
lineage, ids, or `player_name_display`. A traded season's aggregate shows
`source_team_code` like `2TM` with `is_multi_team: true`, and its stints list
the real team codes in code order. `GET /api/v1/health/ready` stays 200.

## Manual sad path

1. `GET /api/v1/players/unknown01/seasons/2008/regular/aggregate/totals` and
   `GET /api/v1/players/jamesle01/seasons/1990/regular/aggregate/totals`.
2. `GET .../2008/playoffs/aggregate/totals`, `.../2008/regular/aggregate/roster`,
   `.../twenty/regular/stints/totals`, and `.../2008/regular/stints/totals?page_size=101`.
3. `GET .../2008/postseason/aggregate/totals`.

Expected result: 404 `Player not found`, then 404 `Player season not found`;
422 for every step-2 request; 404 `{"detail": "Not Found"}` for postseason
until F6-014. A season with membership but no stint stat row returns 200 with
`items: []`; a missing aggregate row returns 404 `Statistics not found`.

## Known limitations

- All automated evidence uses SQLite fixtures and a disposable PostgreSQL
  database. On 2026-10-25, after `nba` reached `0009` with season 2026, a
  read-only `TestClient` smoke run against `nba` (host `127.0.0.1`) returned:
  readiness 200; all 16 routes 200 for `jamesle01` 2008 (`fg_pct` `0.484` as a
  number, no `player_name_display` or lineage); `jamesle01` 2026 per-game 200
  (`LAL`, 60 games); `bradlto01` 2026 aggregate `2TM` with `is_multi_team: true`
  and stints `ATL`, `IND`; the sad-path statuses exactly as listed above. The
  manual steps remain the owner's.
- Postseason paths answer the framework's `Not Found` until F6-014 registers them.
- The card's "stale F4E-024 sentence" was already gone from `API_CONTRACT.md`;
  the marker paragraph that replaced it is rewritten instead.
- Outside the stated scope: `src/nba_data/domain/stat_dimensions.py` (new leaf
  module for `SeasonType` / `StatFamily`, because schemas may not import
  repositories), `src/nba_data/api/app.py` (router registration), and
  `tests/unit/test_api_foundation.py` (the approved-path set).
