---
id: F5-007
title: Key the public teams API on basketball_reference_team_id
areas:
  - api
  - database-read
  - database-schema
  - testing
  - documentation
priority: 65
depends_on:
  - F5-006
read:
  - docs/architecture/API_CONTRACT.md
  - docs/domain/BUSINESS_RULES.md
validation:
  - uv run pytest -ra tests/unit/test_team_api.py tests/unit/test_team_service.py tests/unit/test_team_query_repository.py tests/unit/test_core_models.py tests/integration/test_team_schema_contract_postgres.py
  - uv run ruff check .
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_postgres_local.py
  - uv run pytest
  - uv run python scripts/validate_tasks.py
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
  **Superseded by F4E-014:** revision `0006_synthetic_team_codes` replaces it
  with `ck_core_teams_bref_id_not_synthetic`, which rejects `TOT` and every
  multi-team marker. Use the new name — the old one no longer exists at head.
- The loader always writes the code
  (`src/nba_data/scraping/loaders/team_season.py:46`), so null rows are not
  expected in practice — but nothing prevents one.

Migration head is **`0006_synthetic_team_codes`**, not the `0005` this card was
written against — F4E-014 landed `0006` afterwards. The new revision chains from
`0006`. Confirm with `uv run alembic heads` before writing it, since another card
may land ahead of this one again.

# Human decisions or resources

- None.

# Acceptance criteria

- `GET /api/v1/teams/{basketball_reference_team_id}` resolves a team by its
  Basketball Reference code. The path parameter is a string, and the route no
  longer accepts the surrogate integer.
- Lookup by code is **exact and case-sensitive**, which is what `F5-006` settled:
  `/api/v1/teams/ATL` resolves and `/api/v1/teams/atl` returns 404. A test covers
  both directions explicitly.
- An unknown code returns 404 with the existing `"Team not found"` detail shape.
- A code that is syntactically impossible (empty, over 10 characters, containing
  a path separator) returns 404 or 422 rather than a 500.
- `TOT` is not resolvable through the route, and a test asserts it.
- `franchise_id` is absent from `TeamResponse`. No test fabricates it any more.
- `team_id` is **absent** from `TeamResponse`. `F5-006` withdrew it from v1; see
  *Fields withdrawn from v1* in `docs/architecture/API_CONTRACT.md`. The OpenAPI
  schema matches and no test asserts the field.
- `db/repositories/queries/teams.py` gains a lookup by natural key; `get_team` by
  surrogate id is removed if nothing else calls it, rather than left dead.
- A new Alembic revision chained from `0006_synthetic_team_codes` — the head, not
  the `0005` this card originally named — makes
  `core.teams.basketball_reference_team_id` `NOT NULL`, with a working
  `downgrade()` that restores nullability. Chaining from `0005` would branch the
  history against F4E-014's revision.
- `db/models/core.py` changes the column to `Mapped[str]` with
  `nullable=False`, and `tests/unit/test_core_models.py` asserts it.
- The migration is **created but not applied** to any shared database.
- The number of `core.teams` rows with a null `basketball_reference_team_id` in
  the local dev database is counted and recorded in `# Review evidence`, even
  when it is zero. A non-zero count stops the card and is reported rather than
  repaired unilaterally — see `# Impact`.
- The offline/local validation commands above pass, including the full suite.
- A relocation case (SEA/OKC or NJN/BRK) is covered by a test asserting the
  agreed behaviour: two separate teams, independently reachable by their own
  codes, with no link between them.
- The list route's deterministic ordering still holds and is still asserted, and
  its tie-breaker **changes from `Team.id` to `basketball_reference_team_id`**.
  `F5-006` documents the ordering as `current_name ASC,
  basketball_reference_team_id ASC`; `db/repositories/queries/teams.py:11` still
  orders on the surrogate, which stays deterministic and therefore passes the
  existing assertion while contradicting the contract. Change it and assert the
  new tie-breaker directly.
- `tests/integration/test_api_postgres.py` is updated in the same card. It asserts
  both withdrawn fields today — `team_id` and `franchise_id` in the by-id response
  body — and it addresses a team through `/api/v1/teams/{surrogate int}`, a route
  shape this card removes. It must fetch by `basketball_reference_team_id`
  instead, and its response bodies must match the narrowed `TeamResponse`.
  Its pagination test reads `item["team_id"]` to prove no team is served on two
  pages; that identity check moves to the natural key rather than being dropped.

# Scope

`src/nba_data/api/routers/teams.py`, `src/nba_data/api/schemas/teams.py`,
`src/nba_data/api/services/teams.py`,
`src/nba_data/db/repositories/queries/teams.py`, `src/nba_data/db/models/core.py`
(nullability of one column only), a new file under `alembic/versions/`,
`tests/unit/test_team_api.py`, `test_team_service.py`,
`test_team_query_repository.py`, `test_core_models.py`, and
`tests/integration/test_api_postgres.py`.

The integration module is in scope because it asserts the two fields `F5-006`
withdrew and routes teams by the surrogate id.

**Widened by the corrective extension for PR 25** (see that section below). The
earlier statement that `tests/integration/test_api_postgres.py` was the only
file outside `tests/unit/` this card may touch no longer holds: repairing the
PostgreSQL lane requires shared integration fixtures, the CI job, the local
validator, and the durable testing document. The corrective scope adds:

- `tests/integration/conftest.py` (new);
- `tests/integration/test_api_postgres.py`;
- `tests/integration/test_synthetic_team_code_constraints_postgres.py`;
- `tests/integration/test_team_season_loader_postgres.py`;
- `tests/integration/test_api_unreachable_database.py` (documentation only);
- `tests/integration/test_team_schema_contract_postgres.py` (new);
- `tests/unit/test_team_api.py`, `tests/unit/test_team_service.py`,
  `tests/unit/test_team_query_repository.py`, `tests/unit/test_core_models.py`;
- `scripts/validate_postgres_local.py`;
- `.github/workflows/ci.yml`;
- `docs/validation/TESTING_STRATEGY.md`;
- this task card.

Nothing under `src/nba_data/` or `alembic/` is in the corrective scope.

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
column is `NOT NULL`. The one integration module that seeds teams,
`tests/integration/test_api_postgres.py`, always sets the code, so the migration
itself does not break it — what breaks it is the route and response change, which
is why it is in `# Scope` above rather than only mentioned here.

The local dev database is at `0006_synthetic_team_codes` (the head) as of
2026-08-17, so the integration suite runs rather than skipping. That is what makes
the null-key count below a real measurement instead of a skipped one.

`db/repositories/core.py:58` already looks teams up by the same code; check
whether the new read-only query duplicates it and reuse rather than fork.

The `NOT NULL` migration will fail on any existing database that holds a team row
with a null code. Run a count of such rows against the local dev database before
writing the migration and record the number in `# Review evidence` — if any exist,
stop and report rather than deciding unilaterally how to fix them.

# Implementation notes

Every team decision is already resolved: the six recorded in `F5-006`'s
`# Human decisions or resources`, plus the `team_id` withdrawal and the exact,
case-sensitive lookup that `F5-006` settled in the contract's *Team identity* and
*Fields withdrawn from v1* sections. Read them there rather than re-deriving them.

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

# Corrective extension for PR 25 — 2026-08-21

## Why the card came back from done

PR 25 is red. Its `Offline unit tests` job passes and its
`PostgreSQL integration` job fails, for both GitHub workflow event types.

- Starting SHA: `1cedc0d2e9a7f911d5b961f006703344a1dcae68`
- Push run (event `push`):
  <https://github.com/alejandrou/NBA_ML-./actions/runs/32304764872>
- Pull-request run (event `pull_request`):
  <https://github.com/alejandrou/NBA_ML-./actions/runs/32304864614>
- Offline job baseline: `740 passed, 23 deselected`
- PostgreSQL job baseline: `18 failed, 5 passed`

## Root causes of the 18 failures

1. **Seventeen** parametrized cases in
   `tests/integration/test_synthetic_team_code_constraints_postgres.py` seed a
   parent team with `_seed_parents()`, which inserts `core.teams` supplying only
   `current_name`. Revision `0007_team_bref_id_not_null` makes
   `basketball_reference_team_id` `NOT NULL`, so every one of those cases now
   fails on the parent insert before it ever reaches the synthetic-code
   constraint it exists to test.
2. **One** failure in `tests/integration/test_team_season_loader_postgres.py`,
   which validated the schema against a hard-coded `compatible_revisions`
   whitelist ending at `0006_synthetic_team_codes`. With the require-flag set,
   the current head `0007_team_bref_id_not_null` is rejected as incompatible and
   the skip becomes a failure.

Both are test-harness defects. Neither indicates a defect in the API, the ORM
schema, or migration `0007`.

## Corrective scope

- **Safety.** PostgreSQL integration tests must not connect without an explicit
  opt-in flag (`NBA_DATA_TEST_DATABASE=1`) *and* a disposable database name
  (exactly `nba_test_ci`, or prefixed `nba_test_tmp_`). Both are checked before
  any Engine is constructed.
- **Isolation.** Every database-mutating test receives a function-scoped
  Connection inside an outer transaction that is always rolled back. Sessions
  join it through savepoints and cannot commit it. API seed rows are written
  through that same Connection and are never committed.
- **Tests.** Shared `tests/integration/conftest.py`; dynamic Alembic-head
  resolution replacing every module-local whitelist; an exact PostgreSQL `23502`
  NOT NULL diagnostic regression for
  `core.teams.basketball_reference_team_id`; stronger vertical teams coverage,
  including the `/api/v1/teams/1` surrogate-key 404 regression.
- **CI.** The PostgreSQL job runs against `nba_test_ci` and sets both flags, so
  environment-related skips become failures.
- **Validator.** `scripts/validate_postgres_local.py` sets both flags, runs the
  whole `tests/integration` directory, and verifies every mapped `core` table is
  empty afterwards.
- **Documentation.** One authoritative PostgreSQL section in
  `docs/validation/TESTING_STRATEGY.md`.

## Guardrail

No production API contract, ORM schema, or Alembic migration behavior changes.
The corrective diff against the starting SHA must be empty under `src/nba_data/`
and `alembic/`.

## Corrective acceptance criteria

- The 18 PostgreSQL failures are gone because the harness defects are repaired,
  not because assertions or safety gates were weakened.
- Every accepted and rejected synthetic-code case executes against real
  PostgreSQL at the current head.
- Loader idempotency counts are preserved exactly.
- The NOT NULL contract is asserted by SQLSTATE, schema, table, and column, not
  by the mere existence of an `IntegrityError`.
- Without the safety flag, PostgreSQL tests skip *before* constructing an Engine
  and name the missing flag; in required mode the same condition fails.
- Every mapped `core` table is empty before and after the integration session.
- `uv run python scripts/validate_postgres_local.py` exits 0 and drops only its
  generated `nba_test_tmp_*` database.
- Both CI jobs are green for both the `push` and `pull_request` events.

## Migration-data safety limitation

`0007_team_bref_id_not_null` uses `ALTER COLUMN ... SET NOT NULL` with no
backfill. The disposable, empty scratch database used by this correction proves
the fresh-schema contract only; it cannot prove that an arbitrary populated
database is ready for the migration. Before any separately owner-authorized
application of `0007` to a persistent target, run this read-only preflight
against that exact target:

```sql
SELECT count(*)
FROM core.teams
WHERE basketball_reference_team_id IS NULL;
```

`0` satisfies the data precondition; anything greater stops the migration for a
separate remediation decision with the user. This correction runs no such query
against any persistent database.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Corrective extension evidence (2026-08-21)

### Safety-gate negative checks

Expected-negative policy checks, not green-suite commands. Each used a sentinel
URL (`postgresql+psycopg://nba:nba@localhost:1/definitely_not_a_test_db`) whose
port and database name are both wrong, so any connection attempt would have been
visible.

| Environment | Command | Outcome |
|---|---|---|
| Both flags unset | `uv run pytest -ra tests/integration/test_team_schema_contract_postgres.py` | `1 skipped` in 0.02s; reason names `NBA_DATA_TEST_DATABASE` |
| `NBA_DATA_REQUIRE_POSTGRES_INTEGRATION=1`, safety flag absent | same | `1 error` at setup in 0.02s; same actionable message |
| `NBA_DATA_TEST_DATABASE=1`, unsafe database name | same | `1 error` at setup in 0.02s; message names `'definitely_not_a_test_db'` and the two accepted forms |

No output contained `connection refused`, `could not connect`, or any other
driver diagnostic, confirming all three decisions were made before an Engine was
constructed.

### Ordered validation sequence

1. `uv run pytest -ra tests/unit/test_team_api.py tests/unit/test_team_service.py tests/unit/test_team_query_repository.py tests/unit/test_core_models.py tests/integration/test_team_schema_contract_postgres.py`
   → exit 0, **24 passed, 1 skipped**, 0 failed, 0 deselected. The single skip is
   the PostgreSQL contract test declining to connect without the safety flag,
   which is the intended local behaviour; it executes for real in step 4.
2. `uv run ruff check .` → exit 0, all checks passed.
3. `uv run pytest -m "not integration and not live"` → exit 0,
   **743 passed, 24 deselected**, 0 failed, 0 skipped. (Baseline was
   `740 passed, 23 deselected`: +3 offline from six new vertical teams tests less
   three vertically-redundant mocked router tests, and +1 deselected from the new
   PostgreSQL schema-contract module.)
4. `uv run python scripts/validate_postgres_local.py` → exit 0.
   - Scratch database created and dropped: one generated `nba_test_tmp_*` name
     (`nba_test_tmp_26adf583c10b49cf` on the recorded run). No credentials
     recorded; the configured source database was never migrated, seeded, or
     dropped.
   - `alembic upgrade head`, `alembic check`, `alembic downgrade -1`,
     `alembic upgrade head`, `alembic check` all green — the `0007` round trip
     works on real PostgreSQL.
   - `uv run pytest -ra tests/integration` collected the whole directory:
     **24 passed, 0 failed, 0 skipped**. No environment, safety, or head skip
     occurred in required mode, so every database-dependent test really ran.
   - Post-run empty check over every mapped `core` table passed, independently of
     the in-process session guard.
5. `uv run pytest` with both flags absent from the shell → exit 0,
   **744 passed, 23 skipped**, 0 failed. All 23 skips are the safety-flag skip and
   name it. `test_api_unreachable_database.py` still executed (it is the 744th).
   No live test ran.
6. `uv run python scripts/validate_tasks.py` → exit 0, F5-007 the only
   active/review card.

### Diff hygiene

- `git diff --check` → exit 0, no whitespace errors.
- `git diff 1cedc0d2e9a7f911d5b961f006703344a1dcae68 -- src/nba_data alembic`
  → **empty**. The corrective extension changed no production source and no
  migration.
- Changed paths: `.github/workflows/ci.yml`,
  `docs/validation/TESTING_STRATEGY.md`, `scripts/validate_postgres_local.py`,
  five `tests/integration/` modules (two new), three `tests/unit/` modules, and
  this card. No `.env`, secrets, `data/`, `reports/`, dumps, logs, caches, or
  IDE files. No legacy-path or unrelated refactor.

### Behavioral evidence

Each item below is asserted by a named test that passed in the runs above.

- **Surrogate-key regression.** `/api/v1/teams/BBB` returns 200 for the row
  stored at internal `id=1`; `/api/v1/teams/1` then returns 404 with exactly
  `{"detail": "Team not found"}` — a numeric path segment is a natural key that
  no team holds, not a database id.
- **Case sensitivity and unresolvable codes.** `AAA` resolves; `aaa`, `UNKNOWN`,
  and the synthetic marker `TOT` each return 404 with the exact documented body.
- **Ordering.** The collection is served `current_name` then
  `basketball_reference_team_id`. The two `Bulls` rows are stored at ids 3 and 1
  precisely so that surrogate ordering would produce the wrong sequence.
- **Pagination and empty pages.** Three pages partition five teams with no key
  served twice, page metadata echoed on every page, and a valid page past the end
  returns 200 with `items: []` and an unchanged total. The default `page_size` of
  50 is pinned on the request that omits it.
- **Relocation identity.** SEA and OKC are independently reachable with no
  lineage field linking them.
- **Withdrawn fields.** Neither `team_id` nor `franchise_id` appears in any
  detail or collection item, and the OpenAPI `TeamResponse` schema carries
  exactly the three approved properties.
- **Invalid input and GET-only.** Empty and extra path segments 404, an
  11-character code 422, and POST/PUT/PATCH/DELETE all 405.
- **Sanitized database error.** A real failing query through the genuine
  repository path returns a fixed `{"detail": "Internal Server Error"}` 500 that
  leaks neither the table name nor the statement.
- **Exact PostgreSQL NOT NULL diagnostic.** Inserting a team with no
  `basketball_reference_team_id` raises SQLSTATE `23502` reporting schema `core`,
  table `teams`, column `basketball_reference_team_id` — asserted on the psycopg
  diagnostic, not merely on the exception class.
- **Loader idempotency.** Loading the same batch twice yields exactly one Season,
  Team, TeamAlias, TeamSeason and PlayerTeamSeason, and exactly two Players and
  PlayerSeasons, all counted by domain or natural key.
- **Synthetic-code constraints.** All eight rejected values
  (`TOT`, `tot`, ` 5TM `, `2TM`, `5TM`, `10TM`, `999TM`, `99999999TM`) and all
  nine accepted lookalikes (`BOS`, `CHO`, `0TM`, `1TM`, `02TM`, `TM`, `1T2M`,
  `T2M`, `2MT`) behave correctly across all four guarded columns, each asserted
  against the exact constraint name PostgreSQL reports.

### Known limitations

- PostgreSQL sequence values advance inside rolled-back tests. Surrogate ids are
  therefore never used as evidence of cleanup or ordering. This is safe only
  because every accepted database is destroyed.
- The disposable empty-database lane does not prove migration readiness for an
  arbitrary populated target. See the migration-data safety limitation above.
- Any future application of `0007` to a persistent database needs separate owner
  authorization and the NULL-count preflight.
- `scripts/validate_database.sh` points at the developer's ordinary local
  database, which is not an approved test database; its integration step now
  skips rather than writing there. `scripts/validate_postgres_local.py` is the
  supported local command.
- No live scraping, Basketball Reference contact, or shared-database validation
  was performed.

### GitHub implementation evidence

Implementation SHA `7d181982c9b59950bef0753b4c9f6a07ac5ae03c`, pushed to
`feature/F5-007-key-teams-api-natural-key`, reusing PR 25. Each pushed head
produces two runs; both are recorded separately below and both are green.

| | Push event | Pull-request event |
|---|---|---|
| Run URL | <https://github.com/alejandrou/NBA_ML-./actions/runs/32509790309> | <https://github.com/alejandrou/NBA_ML-./actions/runs/32509794520> |
| Overall conclusion | success | success |
| Offline unit tests | success — Ruff clean; `collected 767 items / 24 deselected / 743 selected`, **743 passed, 24 deselected**, 0 failed, 0 skipped | success — identical counts |
| PostgreSQL integration | success — **24 passed, 0 failed, 0 skipped** | success — identical counts |

Both runs applied `0001` through `0007` cleanly, reported
`No new upgrade operations detected.` on `alembic check`, and re-applied
`0006_synthetic_team_codes -> 0007_team_bref_id_not_null` on the
downgrade/upgrade round trip with a second clean `alembic check`.

The PostgreSQL job ran with `NBA_DATA_TEST_DATABASE=1` and
`NBA_DATA_REQUIRE_POSTGRES_INTEGRATION=1` against `nba_test_ci`. In required
mode every environment condition is a failure rather than a skip, so
`0 skipped` is positive evidence that all 24 database-dependent tests really
executed — including the `23502` NOT NULL diagnostic, loader idempotency, and
all seventeen synthetic-code cases that were failing at the starting SHA.

Compared with the starting SHA `1cedc0d`: the PostgreSQL job went from
`18 failed, 5 passed` to `24 passed`, and the offline job from
`740 passed, 23 deselected` to `743 passed, 24 deselected`.

## Original F5-007 review evidence (historical, 2026-08-17)

Preserved as the record of the change PR 25 originally shipped. The counts below
predate the corrective extension and are not re-run by it.

### Automated validation

- Command: read-only SQLAlchemy count of
  `core.teams.basketball_reference_team_id IS NULL` against the configured local
  development database.
- Result: `0` null-key rows. No data was changed.
- Command: `uv run pytest tests/unit/test_team_api.py tests/unit/test_team_service.py tests/unit/test_team_query_repository.py tests/unit/test_core_models.py`
- Result: `21 passed`.
- Command: `uv run alembic heads`
- Result: `0007_team_bref_id_not_null (head)`.
- Command: `uv run alembic upgrade 0006_synthetic_team_codes:0007_team_bref_id_not_null --sql`
  and `uv run alembic downgrade 0007_team_bref_id_not_null:0006_synthetic_team_codes --sql`
- Result: offline SQL generation succeeded; upgrade emits `SET NOT NULL` and
  downgrade emits `DROP NOT NULL`. Neither migration was applied.
- Command: `uv run pytest tests/unit/test_api_foundation.py`
- Result: `7 passed`.
- Command: `uv run ruff check .`
- Result: all checks passed.
- Command: `uv run pytest`
- Result: `742 passed, 21 skipped`. The skipped PostgreSQL cases require the
  configured local database to be at repository head; it remains at
  `0006_synthetic_team_codes` because this task was not authorized to apply the
  new migration.

### Manual happy path

1. Against a disposable database already migrated to `0007`, start the read API
   and request `GET /api/v1/teams/ATL`.
2. Request `GET /api/v1/teams/SEA` and `GET /api/v1/teams/OKC` when both codes
   are present.
3. Request `GET /api/v1/teams?page=1&page_size=100` and inspect teams sharing a
   `current_name`.

Expected result: detail responses contain only
`basketball_reference_team_id`, `current_abbreviation`, and `current_name`;
SEA and OKC are independently reachable with no lineage field; the collection
orders by `current_name` and then `basketball_reference_team_id`.

### Manual sad path

1. Request `GET /api/v1/teams/atl` and `GET /api/v1/teams/UNKNOWN`.
2. Request `GET /api/v1/teams/TOT` and `GET /api/v1/teams/`.
3. Request an 11-character code and a path containing an extra separator, such
   as `GET /api/v1/teams/ABCDEFGHIJK` and `GET /api/v1/teams/ATL/extra`.

Expected result: lowercase, unknown, `TOT`, empty, and separator-containing
paths return 404; the overlong code returns 422; none returns 500.

### Known limitations

- The configured local PostgreSQL database remains at revision
  `0006_synthetic_team_codes`. Migration-dependent integration tests therefore
  skip until an owner-approved environment is migrated to `0007`.
