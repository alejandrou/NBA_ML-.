---
id: F6-022
title: Harden the player identity routes on PostgreSQL and real data
track: app
areas:
  - api
  - database-read
  - testing
priority: 78
depends_on:
  - F6-012
read:
  - tasks/done/F6-012-serve-the-player-and-player-season-identity-resources.md
  - docs/architecture/API_CONTRACT.md
  - src/nba_data/db/repositories/queries/players.py
  - src/nba_data/api/routers/players.py
  - src/nba_data/db/models/core.py
  - tests/integration/conftest.py
  - tests/integration/test_api_postgres.py
  - tests/unit/test_player_query_repository.py
  - tests/unit/test_player_api.py
validation:
  - uv run pytest tests/unit/test_player_query_repository.py tests/unit/test_player_api.py tests/unit/test_player_service.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - The measurements against the persistent `nba` database are read-only SELECT and EXPLAIN statements (no ANALYZE on a write, no DDL, no DML). Nothing on this card writes to `nba`.
  - Any index or constraint the measurements call for is a `data` track migration. This card only writes its handoff card; it never authors a revision.
---

# Goal

Close the gaps that F6-012 shipped with, so the four player identity routes are
proven on PostgreSQL and against the real `nba` data before F7-003 builds pages
on them:

1. The routes have no PostgreSQL integration coverage.
2. Nothing makes a season's `teams` come from that same season.
3. An empty id on a nested path gets the framework's generic 404 instead of
   the contract's fixed string.
4. Nobody has checked the players list's `full_name` ordering on the real row
   count.

# Evidence and current state

- F6-012's `## Known limitations` says: "Not run against PostgreSQL: the
  integration lane was not executed in this session."
  `tests/integration/test_api_postgres.py` seeds only teams and seasons and has
  no player case. Every player test runs on in-memory SQLite, and SQLite differs
  from PostgreSQL on collation, on `NULL` ordering, and on how it types
  `COUNT` over a subquery.
- `_with_teams` in `src/nba_data/db/repositories/queries/players.py` joins
  `core.player_team_seasons` → `core.team_seasons` → `core.teams`. It filters
  only on `player_season_id`.
- Nothing in the schema or the writer requires a stint's `team_seasons.season_id`
  to match its `player_seasons.season_id`:
  - `PlayerTeamSeason` in `src/nba_data/db/models/core.py` has foreign keys to
    both rows and no check across them.
  - `get_or_create_player_team_season` in `src/nba_data/db/repositories/core.py`
    accepts any pair.
  - A mismatched row would put a team from another year in a season's `teams`.
  - Whether `nba` holds any such row today has not been checked.
- `GET /api/v1/players/` returns the fixed `{"detail": "Player not found"}`
  through `reject_empty_player_id`. `GET /api/v1/players//seasons` and
  `GET /api/v1/players//seasons/2004` match no route. They fall through to
  Starlette's generic `{"detail": "Not Found"}`, which does not follow the
  contract's rule that every 404 detail is a fixed string.
- `list_players` orders by `full_name, basketball_reference_player_id` on every
  page. `core.players` has an index only on the unique id. The cost on the real
  row count has never been measured.

# Human decisions or resources

- None.

# Acceptance criteria

- **PostgreSQL coverage.** `tests/integration/test_api_postgres.py` gains a
  player seed and these cases, all passing under `bash scripts/validate_database.sh`:
  - **Seed.** Commit nothing: seed inside the rolled-back connection, as the
    existing seed does. Include:
    - at least three players whose `full_name` ties or differs only in case or
      accents;
    - one player with a null `basketball_reference_player_id`;
    - one player with no seasons;
    - one multi-team NBA season;
    - one ABA season.
  - **`/players`.** Assert the exact order and `total`. A null-id player is
    never listed or counted. Paging with `page_size=1` never repeats or skips a
    player.
  - **`/players/{id}`.** An exact id returns 200. The uppercase id, a surrogate
    id, and a slug each return 404 with the fixed string.
  - **`/players/{id}/seasons`.** Seasons come newest first, NBA only. `total`
    counts NBA seasons only. The multi-team season's `teams` is sorted
    ascending. The player with no seasons gets 200 with an empty page.
  - **`/players/{id}/seasons/{year}`.** A present year returns 200. An ABA-only
    year and an absent year each return 404 "Player season not found".
  - **`/health/ready`.** Returns 200 with all five required tables present.
- **Season-consistent teams.** `_with_teams` adds
  `TeamSeason.season_id == PlayerSeason.season_id` to its join, still in one
  query per page.
  - A unit test seeds a stint whose team season belongs to another year and
    asserts that team is absent from `teams`.
  - The existing statement-count test still passes.
- **Fixed 404 strings.** `GET /api/v1/players//seasons` and
  `GET /api/v1/players//seasons/{year}` return 404 `{"detail": "Player not found"}`.
  - They are routes with `include_in_schema=False`, like `reject_empty_player_id`.
  - Unit tests pin both, and pin that the OpenAPI path list is unchanged.
- **Real-data checks.** The review evidence records each of these, run
  read-only against `nba`:
  - The count of `core.player_team_seasons` rows whose team season and player
    season point at different seasons. If it is not zero, create a `data`
    planning card for the loader or a constraint, add a `tasks/CROSS_TRACK.md`
    Open entry, and name it under `# Cross-track impact`.
  - `EXPLAIN (ANALYZE, BUFFERS)` of the first-page and a deep-page
    `list_players` statements, with `count(*)` of `core.players`. If a page
    takes more than 50 ms, hand off a `full_name` index the same way.
    Otherwise, record the numbers and close the concern.
  - The F6-012 manual happy and sad paths, run through `uv run nba-data serve`
    against `nba`, with every status and body recorded as observed.

# Scope

- `src/nba_data/db/repositories/queries/players.py` (`_with_teams` only).
- `src/nba_data/api/routers/players.py` (the two empty-id routes).
- `tests/integration/test_api_postgres.py`.
- `tests/unit/test_player_query_repository.py`, `tests/unit/test_player_api.py`.
- A `data` planning card and a `tasks/CROSS_TRACK.md` entry, only if a
  measurement calls for one.

# Out of scope

- **Response shapes, keys, ordering rules, and NBA scope.** The contract stays
  exactly as F6-012 served it.
- **The service's exception-based not-found pattern.** It differs from the
  teams service on purpose: `/seasons/{year}` has two distinct 404s. F6-012's
  review evidence records why.
- **Making `basketball_reference_player_id` NOT NULL, adding a cross-season
  constraint, or adding an index.** These are `data` track migrations; this card
  only hands them off.
- **Name search.** F6-019 owns it.
- **The statistics routes.** F6-013 and F6-014 own them.

# Impact

- Player season `teams` can only shrink, and only when a row is inconsistent,
  which is a data defect. No response field changes.
- Two nested empty-id paths change from the generic 404 to the fixed one.
- The PostgreSQL integration lane grows, both locally and in CI.

# Cross-track impact

- None.

# Implementation notes

- **Integration seed.** Follow the existing `api_seed` fixture: raw
  `text()` inserts through `postgres_connection`, natural keys in the returned
  dataclass, and no surrogate id outside the fixture. Give the player seed its
  own fixture so the team tests keep their exact totals.
- **Collation.** Write the ordering assertion from what PostgreSQL returns
  under the lane's collation, and say in a comment which collation that is.
  If it differs from the SQLite unit test's order, that difference is the
  finding: record it, and do not bend either test to hide it.
- **Where the season check goes.** Put it in the teams join, not in a
  post-filter in Python. The page must stay at two SELECTs.
- **Empty-id route order.** Declare the empty-id routes before the
  parameterised ones only if Starlette's matching needs it. Confirm with a test
  rather than assuming.
- **`EXPLAIN (ANALYZE)` is safe here.** It executes the statement, but these
  are SELECTs on `nba`, so it writes nothing. Do not run it on anything else.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md`: one sentence saying a player season's
  `teams` holds only stints of that same season.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
