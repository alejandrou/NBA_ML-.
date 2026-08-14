---
id: F5-007
title: Key the public teams API on basketball_reference_team_id
areas:
  - api
  - database-read
  - database-schema
priority: 65
depends_on:
  - F5-006
read:
  - docs/architecture/API_CONTRACT.md
  - docs/domain/BUSINESS_RULES.md
validation:
  - uv run pytest tests/unit/test_team_api.py tests/unit/test_team_service.py tests/unit/test_team_query_repository.py tests/unit/test_core_models.py
  - uv run ruff check .
  - uv run pytest
critical_actions:
  - Applying the NOT NULL migration to a shared or production-like database. This card creates the migration file only; it never applies it.
---

# Goal

Make the teams API match the contract `F5-006` settles: route on
`basketball_reference_team_id`, drop `franchise_id` from the response, and add
the migration that makes the natural key non-nullable.

# Evidence and current state

The route, service, and query repository all key on the surrogate today:

- `src/nba_data/api/routers/teams.py:28` declares `/{team_id}` with
  `team_id: Annotated[int, Path(ge=1)]`.
- `src/nba_data/api/services/teams.py:24` calls `team_queries.get_team(session, team_id)`
  and `:30` maps `team.id` to the response field.
- `src/nba_data/db/repositories/queries/teams.py:26` filters `Team.id == team_id`.
- `src/nba_data/api/schemas/teams.py:4-9` returns `team_id`,
  `basketball_reference_team_id`, `current_abbreviation`, `current_name`, and
  `franchise_id`.

`franchise_id` is always `null` in practice: it exists in `db/models/core.py:45`
and migration `0001`, but nothing in `src/` writes it. The unit tests fabricate
values such as `"bulls"` and `"hawks"`, so the test suite is currently the only
place it is ever non-null — expect those fixtures to need updating rather than
merely passing.

On the database side, verified against the migrations:

- Uniqueness is already enforced: `0002_core_team_player_season.py:20-25` creates
  `uq_core_teams_bref_id`. **No new unique constraint is needed** — the natural
  key is already safe to route on.
- The column is still nullable: `0001_initial_raw_core.py:80` and
  `db/models/core.py:43` (`Mapped[str | None]`).
- `TOT` is already rejected by `ck_core_teams_bref_id_not_tot` (`0002:26-31`).
- The loader always writes the code
  (`src/nba_data/scraping/loaders/team_season.py:46`), so null rows are not
  expected in practice — but nothing prevents one.

Latest migration head is `0005_postseason_stats_tables.py`; the new revision
chains from it.

# Human decisions or resources

- None.

# Acceptance criteria

- `GET /api/v1/teams/{basketball_reference_team_id}` resolves a team by its
  Basketball Reference code. The path parameter is a string, and the route no
  longer accepts the surrogate integer.
- Lookup by code is case-insensitive or documented as case-sensitive — whichever
  `F5-006` states — and a test covers the chosen behaviour explicitly.
- An unknown code returns 404 with the existing `"Team not found"` detail shape.
- A code that is syntactically impossible (empty, over 10 characters, containing
  a path separator) returns 404 or 422 rather than a 500.
- `TOT` is not resolvable through the route, and a test asserts it.
- `franchise_id` is absent from `TeamResponse`. No test fabricates it any more.
- `team_id` is handled as `F5-006` specifies — retained as an opaque non-key
  field or removed — and the OpenAPI schema matches.
- `db/repositories/queries/teams.py` gains a lookup by natural key; `get_team` by
  surrogate id is removed if nothing else calls it, rather than left dead.
- A new Alembic revision chained from `0005_postseason_stats_tables` makes
  `core.teams.basketball_reference_team_id` `NOT NULL`, with a working
  `downgrade()` that restores nullability.
- `db/models/core.py` changes the column to `Mapped[str]` with
  `nullable=False`, and `tests/unit/test_core_models.py` asserts it.
- The migration is **created but not applied** to any shared database.
- The offline/local validation commands above pass, including the full suite.
- A relocation case (SEA/OKC or NJN/BRK) is covered by a test asserting the
  agreed behaviour: two separate teams, independently reachable by their own
  codes, with no link between them.
- The list route's deterministic ordering still holds and is still asserted.

# Scope

`src/nba_data/api/routers/teams.py`, `src/nba_data/api/schemas/teams.py`,
`src/nba_data/api/services/teams.py`,
`src/nba_data/db/repositories/queries/teams.py`, `src/nba_data/db/models/core.py`
(nullability of one column only), a new file under `alembic/versions/`, and
`tests/unit/test_team_api.py`, `test_team_service.py`,
`test_team_query_repository.py`, `test_core_models.py`.

# Out of scope

Applying the migration to any shared, persistent, or production-like database —
that is the user's call, listed under `critical_actions:`. Adding a `league`
column or scoping teams to NBA: `F5-006` settles that teams are deliberately
league-agnostic. Populating `franchise_id`. Changing the loader, `team_aliases`,
or `TeamSeason`. Players, statistics, and write routes. Re-opening any `F5-006`
decision — if the contract turns out to be wrong, fix the contract, do not
diverge from it silently.

# Impact

Breaking change to the shipped `GET /api/v1/teams/{team_id}` route and to the
`TeamResponse` body, taken deliberately before any client exists per `F5-006`
decision 4. The OpenAPI surface changes. Any integration test or fixture that
builds a team without `basketball_reference_team_id` will start failing once the
column is `NOT NULL` — check `tests/integration/` as well as the unit tests
listed above.

`db/repositories/core.py:58` already looks teams up by the same code; check
whether the new read-only query duplicates it and reuse rather than fork.

The `NOT NULL` migration will fail on any existing database that holds a team row
with a null code. Run a count of such rows against the local dev database before
writing the migration and record the number in `# Review evidence` — if any exist,
stop and report rather than deciding unilaterally how to fix them.

# Implementation notes

All four team decisions are already resolved and recorded in `F5-006`'s
`# Human decisions or resources`; read them there rather than re-deriving them.

Do not start until `F5-006` is in `tasks/done/`. This card implements that
contract; starting early means implementing a specification that may still change.

Keep the read path read-only — no flush, no commit, no session mutation in the
query repository, matching the existing `list_teams` / `count_teams` style.

The natural key is 10 characters at most (`String(10)`), which makes it safe as a
path segment, but constrain the path parameter rather than relying on that.

Prefer widening the existing tests over adding a parallel file; the three team
test modules already cover the surrogate path and should end up covering the
natural-key path instead, not in addition.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — if implementation reveals a detail
  `F5-006` did not anticipate (a null-key row that exists, a case-sensitivity
  problem), update the contract in the same branch rather than leaving code and
  document disagreeing.

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
