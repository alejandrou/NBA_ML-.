---
id: F6-012
title: Serve the player and player-season identity resources
track: app
areas:
  - api
  - database-read
  - testing
priority: 95
depends_on:
  - F6-004
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - src/nba_data/api/routers/teams.py
  - src/nba_data/api/services/teams.py
  - src/nba_data/api/schemas/teams.py
  - src/nba_data/db/repositories/queries/teams.py
  - src/nba_data/db/repositories/queries/seasons.py
  - src/nba_data/api/services/readiness.py
  - src/nba_data/db/models/core.py
  - tests/unit/test_team_api.py
  - tests/unit/test_team_service.py
  - tests/unit/test_team_query_repository.py
validation:
  - uv run pytest tests/unit/test_player_api.py tests/unit/test_player_service.py tests/unit/test_player_query_repository.py tests/unit/test_api_readiness.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions: []
---

# Goal

Implement the first four route templates of the player contract — the identity
resources, which read `core` only and touch no `stats` table:

```text
GET /api/v1/players
GET /api/v1/players/{pid}
GET /api/v1/players/{pid}/seasons
GET /api/v1/players/{pid}/seasons/{season_year}
```

This is deliberately the half of the contract that is **not** gated on data
health. The `core.players`, `core.player_seasons`, and `core.player_team_seasons`
tables are current; only the `stats` families are stale, and they belong to
F6-013 and F6-014.

# Evidence and current state

- `docs/architecture/API_CONTRACT.md` carries the settled Players and statistics
  section, written by F6-004. It fixes the key, the casing rule, the bodies, the
  ordering, the status codes, and the non-promises. Nothing in it is
  implemented.
- `db/repositories/queries/` holds `teams.py` and `seasons.py` only. There is no
  player query repository, player service, player schema, or player router.
- `routers/teams.py`, `services/teams.py`, `schemas/teams.py`, and
  `queries/teams.py` are the working four-layer example this card copies:
  router translates HTTP, service orchestrates, query repository reads, schema
  defines the body.
- `routers/teams.py:27-30` registers an explicit `GET /` returning 404 so an
  empty code segment does not fall through to the collection. The player routes
  need the same treatment for an empty `{pid}`.
- `services/readiness.py:24` holds `REQUIRED_TABLES = ("teams", "seasons")` under
  schema `core`. A route whose table is not checked can still 500 against a
  partially migrated database.
- `queries/seasons.py` scopes every season read with `Season.league == "NBA"`
  (`NBA_LEAGUE`); the contract's "Season and team scope" section says every
  player resource inherits that scope.
- `core.players.basketball_reference_player_id` is `String(32)` and still
  `nullable=True` in the model; the contract says a player without one is a data
  defect, never a served row.

# Human decisions or resources

- [x] `/players` enumerates **every** `core.players` row that has a
      `basketball_reference_player_id`, whether or not it has seasons — the same
      set `/players/{pid}` can return. (Owner, 2026-09-23.)
- [x] `/players/{pid}/seasons` lists **every** NBA-scoped `core.player_seasons`
      row of the player, with `teams` possibly empty. (Owner, 2026-09-23.)
- [x] `/players/{pid}/seasons` uses the standard collection envelope with
      `page` / `page_size`: the contract says "All collections use the
      collection envelope" (Ordering and pagination).
- [x] `{pid}` is `Path(min_length=1, max_length=32)`, matching the column. Case
      is not validated: `JAMESLE01` passes validation, matches nothing, and
      returns the contract's 404 `Player not found`.

# Acceptance criteria

- `src/nba_data/db/repositories/queries/players.py` — read-only, never mutates
  its Session:
  - `list_players(session, *, offset, limit)` and `count_players(session)` over
    `core.players` where `basketball_reference_player_id IS NOT NULL`, ordered
    `full_name ASC, basketball_reference_player_id ASC`.
  - `get_player(session, pid)` by exact id match.
  - `list_player_seasons` / `count_player_seasons` for one player, NBA seasons
    only, ordered `season_year DESC`; `get_player_season(session, pid,
    season_year)`.
  - Each season item's `teams`: the `basketball_reference_team_id` values reached
    through `core.player_team_seasons` → `core.team_seasons` → `core.teams`,
    sorted ascending, loaded without one query per season.
- `src/nba_data/api/schemas/players.py` — `PlayerResponse`
  (`basketball_reference_player_id`, `full_name`), `PlayerSeasonResponse`
  (`season_year`, `league`, `teams`), and their list envelopes, in the same
  shape as `TeamListResponse`. No surrogate id, slug, or lineage column.
- `src/nba_data/api/services/players.py` — orchestration mirroring
  `services/teams.py`.
- `src/nba_data/api/routers/players.py`, registered under `/api/v1`:
  - `GET /players` with `page` (≥1) and `page_size` (1–100, default 50).
  - `GET /players/` → 404 `{"detail": "Player not found"}`, excluded from the
    schema.
  - `GET /players/{pid}` → the player, or 404 `Player not found`.
  - `GET /players/{pid}/seasons` → the envelope; 404 `Player not found` when
    the player is unknown; 200 with empty `items` for a known player with no
    seasons.
  - `GET /players/{pid}/seasons/{season_year}` → one season item; 404
    `Player not found` for an unknown player, 404 `Player season not found` for
    a known player without that season; 422 for a non-integer year.
  - Detail strings never interpolate the id, the year, or an exception.
- `REQUIRED_TABLES` in `services/readiness.py` gains `players`,
  `player_seasons`, and `player_team_seasons`; readiness tests updated.
- Offline tests, no PostgreSQL:
  - `tests/unit/test_player_query_repository.py` — ordering, null-id exclusion,
    NBA scope, `teams` composition, Session left unchanged (pattern of
    `test_team_query_repository.py`).
  - `tests/unit/test_player_service.py` and `tests/unit/test_player_api.py` —
    `TestClient` with dependency overrides, every row of the status table above,
    exact-case 404, empty-`{pid}` 404, pagination bounds, and a body-key check
    proving no private column leaks.
- The contract's "Specified, not yet served" marker narrowed to the statistics
  routes.

# Scope

`src/nba_data/api/routers/`, `src/nba_data/api/services/`,
`src/nba_data/api/schemas/`, `src/nba_data/db/repositories/queries/`,
`src/nba_data/api/services/readiness.py`, the app registration in
`src/nba_data/api/app.py`, `tests/unit/`, and the marker paragraph in
`docs/architecture/API_CONTRACT.md`.

# Out of scope

Every statistics route and every `stats` table — those are F6-013 and F6-014.
The roster table. Any schema change or migration, including making
`basketball_reference_player_id` NOT NULL (a `data` track change). Any write
path. Name search. Contacting Basketball Reference.

# Impact

- **API:** four new routes; the first `core.players` reads in the application.
- **Readiness:** three tables added to the required list.
- **Data:** none. Read-only.

# Cross-track impact

- None.

# Implementation notes

Follow the teams resource layer for layer rather than inventing a shape. The
contract is the authority on bodies and status codes; do not re-derive them from
the ORM.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — narrow the "Specified, not yet served"
  marker to the statistics routes once these four are live.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command: `uv run pytest tests/unit/test_player_api.py tests/unit/test_player_service.py tests/unit/test_player_query_repository.py tests/unit/test_api_readiness.py`
- Result: 56 passed.
- Command: `uv run ruff check .`
- Result: All checks passed.
- Command: `uv run mypy src/nba_data`
- Result: Success: no issues found in 74 source files.
- Command: `uv run pytest -m "not integration and not live"`
- Result: 1038 passed, 28 deselected.
- Command: `uv run python scripts/validate_tasks.py`
- Result: Task validation passed.

Changes beyond the four new modules: `app.py` registers the router;
`REQUIRED_TABLES` gains the three player tables, with the readiness fake stocked
to match, the list pinned, and one 503 test per new table;
`tests/unit/test_api_foundation.py`'s OpenAPI path allow-list gains the four
player paths (the test exists to fail when a route is added unapproved); and the
contract marker and its required-table sentence are narrowed.

Design choice worth checking: the service raises `PlayerNotFoundError` /
`PlayerSeasonNotFoundError` and the router maps each to its fixed 404 string,
rather than returning `None` as the teams service does, because
`/seasons/{season_year}` has two distinct 404s. Season items come from a typed
projection (`PlayerSeasonIdentity`) built with exactly two SELECTs per page — the
page and its teams — which a test pins by counting statements.

## Manual happy path

1. `uv run nba-data serve`, against the `nba` database at the migration head.
2. `GET http://127.0.0.1:8000/api/v1/health/ready` → 200 `{"status": "ready"}`.
3. `GET /api/v1/players?page_size=5` → envelope ordered by `full_name`, then id;
   `total` is the count of players with an id; each item has only
   `basketball_reference_player_id` and `full_name`.
4. Take a multi-team player (e.g. `jamesle01` if loaded) and
   `GET /api/v1/players/<pid>` → that player.
5. `GET /api/v1/players/<pid>/seasons` → NBA seasons newest first, each
   `{"season_year", "league": "NBA", "teams": [...]}` with uppercase codes
   sorted ascending.
6. `GET /api/v1/players/<pid>/seasons/<a year from step 5>` → that one item.
7. `/docs` lists the four player routes under the `players` tag.

Expected result: every call 200 with the bodies above; no `id`, `slug`, roster,
or lineage key anywhere.

## Manual sad path

1. `GET /api/v1/players/JAMESLE01`, `/api/v1/players/1`, and
   `/api/v1/players/nobody99/seasons` → 404 `{"detail": "Player not found"}`.
2. `GET /api/v1/players/` → 404 `{"detail": "Player not found"}` (not the
   collection, not a redirect).
3. `GET /api/v1/players/<pid>/seasons/1900` → 404
   `{"detail": "Player season not found"}`.
4. `GET /api/v1/players/<pid>/seasons/abc`, `/api/v1/players?page=0`,
   `/api/v1/players?page_size=101`, and a 33-character id → 422.
5. `GET /api/v1/players?page=100000` → 200, empty `items`, unchanged `total`.

Expected result: exactly those statuses and fixed strings; no detail echoes the
id or year.

## Known limitations

- Not run against PostgreSQL: the integration lane was not executed in this
  session. The queries use only joins, `IN`, `COUNT` over a subquery, and
  `ORDER BY`, and every new test runs them for real on SQLite.
- A known player with seasons only in another league gets 200 with an empty
  `items` list, per the owner decision that the list is NBA-scoped.
- `core.players.basketball_reference_player_id` stays nullable in the schema;
  the API filters null rows out, and making the column NOT NULL is data-track
  work outside this card.
