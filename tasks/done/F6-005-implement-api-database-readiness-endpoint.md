---
id: F6-005
title: Implement the API database-readiness endpoint
areas:
  - api
  - database-read
  - testing
priority: 85
depends_on:
  - F6-003
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - src/nba_data/api/app.py
  - src/nba_data/api/routers/health.py
  - src/nba_data/api/dependencies.py
  - src/nba_data/config/settings.py
  - tests/integration/test_api_postgres.py
validation:
  - uv run pytest tests/unit/test_api_readiness.py
  - uv run pytest tests/unit/test_api_foundation.py tests/unit/test_settings.py
  - uv run ruff check .
  - uv run pytest -m "not integration and not live"
critical_actions: []
---

# Goal

Implement `GET /api/v1/health/ready` exactly as F6-003 fixes it in
`docs/architecture/API_CONTRACT.md`, so an operator can distinguish "the process
is alive" from "the database is reachable and migrated".

# Evidence and current state

- F6-003 settles the route, semantics, status codes, bodies, probe timing, and
  timeout setting name. This card implements that contract and changes none of
  it. If the implementation cannot satisfy a stated clause, stop and say so
  rather than quietly redefining the contract.
- `routers/health.py` currently holds one route and imports only
  `HealthResponse`. The readiness route belongs in this same router so both
  operational signals share a namespace.
- `dependencies.py:9-13` already yields one app-owned Session per request and
  closes it. The probe reuses this dependency; it must not call
  `create_db_engine()` itself, which would violate the one-Engine-per-app rule
  in `API_ARCHITECTURE.md`.
- SQLAlchemy Sessions connect lazily, so acquiring the dependency succeeds even
  against a dead database. The connection error surfaces on first execute, which
  is why the probe — not the dependency — must catch it.
- `app.py:41` registers a catch-all `Exception` handler returning a 500. Any
  `SQLAlchemyError` escaping the readiness path becomes a 500 instead of the
  contracted 503, so the probe must catch `SQLAlchemyError` (and the timeout
  case) explicitly.
- `tests/integration/test_api_postgres.py:125-145` already compares
  `SELECT version_num FROM alembic_version` against
  `ScriptDirectory.from_config(Config(...)).get_heads()`. Reuse that approach for
  the runtime schema check; `alembic` is a runtime dependency, so this is legal
  in `src/`.
- `tests/unit/test_api_foundation.py` asserts every OpenAPI path starts with
  `/api/v1/`. `/api/v1/health/ready` complies, but the test may need extending
  if it enumerates the expected route set.

# Human decisions or resources

- None.
  Every semantic decision is fixed by the F6-003 contract.

# Acceptance criteria

- `Settings` gains `api_readiness_timeout_seconds: float = Field(default=2.0, gt=0)`,
  overridable by environment variable like every other setting, covered by a
  case in `tests/unit/test_settings.py`.
- `GET /api/v1/health/ready` exists in `src/nba_data/api/routers/health.py`, is
  GET only, and returns an explicit Pydantic schema — not a bare dict and not an
  ORM model.
- Ready path: the probe executes `SELECT 1`, reads the applied Alembic revision,
  compares it to the migration head, and confirms `core.teams` and
  `core.seasons` exist. All checks pass → 200 `{"status": "ready"}`.
- Not-ready paths return 503 with the exact fixed `detail` strings from the
  contract:
  - connection failure → `"Database unavailable"`;
  - probe exceeded `api_readiness_timeout_seconds` → `"Database readiness check
    timed out"`;
  - connected but revision not at head, or a required table missing →
    `"Database schema not ready"`.
- No 503 body interpolates an exception, driver message, SQL string, DSN,
  credential, or filesystem path. A test asserts the body is byte-for-byte the
  fixed string when the underlying error message contains a password-like
  substring.
- The probe is bounded: a database that accepts a connection but never answers
  returns 503 within the configured timeout rather than hanging the request.
- The underlying failure is logged server-side with its cause, mirroring
  `handle_unexpected_error`.
- `GET /api/v1/health` is unchanged: still 200 `{"status": "ok"}`, still opens no
  Session. A test asserts the liveness route stays green while the readiness
  route reports 503 for the same broken database.
- The readiness route never reaches `handle_unexpected_error`: a test drives a
  raising probe and asserts 503 with the contract body, not 500 with
  `"Internal Server Error"`.
- The OpenAPI document declares both the 200 and 503 responses for the route.
- `tests/unit/test_api_readiness.py` covers ready, unavailable, timeout,
  not-at-head, missing-table, and no-leak, offline, using dependency overrides —
  no PostgreSQL required.
- `tests/integration/test_api_postgres.py` gains a case asserting 200
  `{"status": "ready"}` against the real migrated database, following the
  existing skip/require conventions in that file.
- Startup stays non-blocking: creating the app with an unreachable
  `database_url` still succeeds, and a test asserts it.

# Scope

`src/nba_data/api/routers/health.py`, `src/nba_data/api/schemas/health.py`,
a readiness probe under `src/nba_data/api/services/`,
`src/nba_data/config/settings.py`, `tests/unit/test_api_readiness.py`,
`tests/unit/test_settings.py`, `tests/unit/test_api_foundation.py` if its route
set is enumerated, and `tests/integration/test_api_postgres.py`.

# Out of scope

Changing `GET /api/v1/health`. Changing the readiness contract settled by
F6-003 — if it looks wrong, raise it rather than edit it. Adding auth,
migrations, new tables, write routes, or any other data resource. Making
startup fail on an unreachable database. Contacting Basketball Reference.

# Impact

Adds one public route, one setting, one schema, and one service to the API
surface, and adds 503 to the live status codes. Touches the OpenAPI document,
which `tests/unit/test_api_foundation.py` asserts against. Extends the
PostgreSQL integration lane already gated in CI by F6-001/F6-002, so the
integration job runs one more case.

# Implementation notes

Put the probe in a service, not the router: the router translates HTTP, the
service orchestrates the checks. Keep the three failure causes as distinct
outcomes inside the service so the router maps them to fixed strings without
inspecting exception text.

For the timeout, prefer bounding it in the database rather than racing a thread
— `SET LOCAL statement_timeout` inside the probe's transaction is the direct fit
for the psycopg/PostgreSQL stack already in use, and it makes the timeout the
database's own answer instead of an abandoned in-flight query. Whatever the
mechanism, the requirement is the contract one: bounded by
`api_readiness_timeout_seconds`, returning 503 rather than hanging.

Resolve the migration head through `ScriptDirectory`, matching
`tests/integration/test_api_postgres.py`. Resolve `alembic.ini` by path relative
to the package, not the process working directory — `Settings.scraper_cache_dir`
is already relative and has caused a silent-zero bug elsewhere in this
repository (see F4E-011). Do not repeat that pattern.

The catch-all handler at `app.py:41` is the trap in this task: the readiness
path must handle its own failures completely, or every not-ready case silently
becomes the wrong status code.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — only if implementation proves a clause
  of the F6-003 contract unimplementable as written; otherwise no change.
- None expected beyond that.

Done: `docs/architecture/API_CONTRACT.md` is unchanged — every clause was
implementable as written. `docs/architecture/API_ARCHITECTURE.md` gained one
paragraph under "Health and readiness" recording that connection establishment
carries its own bound, `database_connect_timeout_seconds`, and how it composes
with `api_readiness_timeout_seconds`. `.env.example` lists both settings.

# Review evidence

## What was built

- `src/nba_data/api/services/readiness.py` — the probe. Returns a
  `ReadinessOutcome` (`READY`, `UNAVAILABLE`, `TIMED_OUT`, `SCHEMA_NOT_READY`)
  and never raises, so nothing reaches `handle_unexpected_error`.
- `src/nba_data/api/routers/health.py` — `GET /api/v1/health/ready`, mapping the
  outcome to 200 or to 503 with one of the three fixed strings. `GET
  /api/v1/health` is byte-for-byte unchanged.
- `src/nba_data/api/schemas/health.py` — `ReadinessResponse` and
  `ReadinessErrorResponse`, whose `detail` is a `Literal` of exactly the three
  contract strings, so OpenAPI documents them.
- `src/nba_data/config/settings.py` — `api_readiness_timeout_seconds`,
  default `2.0`, `gt=0`, and `database_connect_timeout_seconds`, default `5.0`,
  `gt=0`.
- `src/nba_data/db/session.py` — `create_db_engine()` now bounds connection
  establishment with libpq's `connect_timeout`. Statement timeouts only start
  once a connection exists, so without this a host that swallows packets hangs
  the request before the probe can run: measured on this machine, an unbounded
  `psycopg.connect` to a blackholed address was still waiting when killed at
  **25s**, while the same address now answers `503` in **2.6s** under a 2s bound.
  This exceeds the card's stated scope, which raised the gap rather than closing
  it; the user asked for it to be fixed on this branch before review.

Timeout mechanism: `SET LOCAL statement_timeout = <ms>` inside the probe's
transaction, as the card recommended, so the bound is PostgreSQL's own answer
rather than an abandoned in-flight query. Migration head is resolved through
`ScriptDirectory` from an `alembic.ini` path derived from the package, and the
ini's relative `prepend_sys_path` is cleared so `from_config` cannot splice the
working directory into a running server's `sys.path`.

## Automated validation

- Command: `uv run pytest tests/unit/test_api_readiness.py`
- Result: **17 passed**
- Command: `uv run pytest tests/unit/test_api_foundation.py tests/unit/test_settings.py`
- Result: **14 passed**
- Command: `uv run pytest tests/unit/test_db_session.py`
- Result: **9 passed**
- Command: `uv run ruff check .`
- Result: **All checks passed!**
- Command: `uv run pytest -m "not integration and not live"`
- Result: **417 passed, 4 deselected**
- Command: `uv run pytest tests/integration/test_api_postgres.py::test_postgres_api_reports_the_database_as_ready`
- Result: **1 passed** against the real migrated local PostgreSQL.
- Command: `uv run pytest tests/integration/test_api_unreachable_database.py`
- Result: **1 passed in 2.64s** — readiness answered `503
  {"detail":"Database unavailable"}` against a blackholed address while liveness
  stayed `200`.
- Command: `uv run pytest tests/integration -m integration`
- Result: **3 passed, 1 error.** The error is the pre-existing
  `test_postgres_api_reads_teams_and_filtered_seasons`, whose fixture refuses to
  run against a populated database ("found 37 team row(s) and 26 season row(s)").
  That is the local database's state, not a regression: the fixture fails before
  seeding and writes nothing. It passes in CI, which uses an empty database.

Two behaviours that unit fakes cannot prove were measured directly against the
running local PostgreSQL:

- The time bound really fires: with the probe bounded at `0.25s`,
  `SELECT pg_sleep(5)` was cancelled at **0.251s** and classified `TIMED_OUT`
  through the real driver's SQLSTATE.
- `tests/unit/test_api_readiness.py` also asserts
  `psycopg.errors.QueryCanceled.sqlstate == "57014"`, so the fake used in the
  timeout test cannot drift away from the driver.

## Manual happy path

1. Start the database and confirm it is at the migration head:
   `docker compose up -d postgres`
2. Run the API: `uv run uvicorn nba_data.api.app:create_app --factory --port 8123`
3. `curl -i http://127.0.0.1:8123/api/v1/health/ready`
4. `curl -i http://127.0.0.1:8123/api/v1/health`
5. Open `http://127.0.0.1:8123/docs` and expand `GET /api/v1/health/ready`.

Expected result: step 3 returns `200` with `{"status":"ready"}`; step 4 returns
`200` with `{"status":"ok"}`; step 5 shows both a `200` and a `503` response
documented, the `503` listing exactly the three fixed `detail` strings.

Observed: steps 3 and 4 returned `{"status":"ready"}` / `{"status":"ok"}`, both
`200`.

## Manual sad path

1. Point the API at a database that does not exist, leaving the server itself
   healthy: `DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/no_such_db`
2. Start the API — it must start, not refuse to boot.
3. `curl -i http://127.0.0.1:8123/api/v1/health/ready`
4. `curl -i http://127.0.0.1:8123/api/v1/health`
5. Read the server log.

Expected result: startup succeeds; step 3 returns `503` with exactly
`{"detail":"Database unavailable"}`; step 4 still returns `200`
`{"status":"ok"}`; the log carries the full driver error while the response body
carries none of it.

Observed: startup took 0.061s with an unreachable database. Readiness answered
`503 {"detail":"Database unavailable"}` in **0.085s**, liveness stayed `200`, and
the driver message naming the host, port, and database appeared only in the log.

Second sad path — a host that never answers at all, which is the case a
statement timeout cannot reach:

1. `DATABASE_URL=postgresql+psycopg://nba:nba@10.255.255.1:5432/nba` (private
   address space, no host behind it).
2. Start the API and `curl -i http://127.0.0.1:8123/api/v1/health/ready`.

Expected result: a `503` within the connect bound, not a hanging request.

Observed: startup took 0.061s; readiness answered `503
{"detail":"Database unavailable"}` in **5.090s** at the default `5.0` bound and
in **2.6s** at a `2.0` bound, liveness stayed `200`. Before this change the same
address left `psycopg.connect` waiting until it was killed at **25s**.
`tests/integration/test_api_unreachable_database.py` locks the behaviour in.

## Known limitations

- **Readiness is bounded by two settings in sequence, not one.** `SET LOCAL
  statement_timeout` bounds the probe once a connection exists;
  `database_connect_timeout_seconds` bounds getting that connection. Worst-case
  latency against a dead host is therefore the sum, roughly `5s + 2s` at the
  defaults, not `api_readiness_timeout_seconds` alone. Both are configurable and
  neither path is unbounded, which is what `API_CONTRACT.md` requires
  ("unreachable **or** unresponsive ... rather than a hanging request"), but an
  operator tuning a Kubernetes probe deadline should size it against the sum.
- **A connect timeout reports `"Database unavailable"`, not the timed-out body.**
  The contract reserves `"Database readiness check timed out"` for exceeding
  `api_readiness_timeout_seconds`; a connect that never completes is a connection
  failure and reports as one. A unit test pins this to
  `psycopg.errors.ConnectionTimeout` so the classification cannot drift.
- **The connect bound is whole seconds and never below 2.** libpq truncates to
  integer seconds and silently treats anything below 2 as 2, so
  `create_db_engine()` rounds the configured value up and floors it at 2 rather
  than implying a `0.5` bound works. It is applied only to PostgreSQL URLs, since
  it is a libpq keyword no other driver accepts — a test creates a SQLite engine
  and connects through it to prove the offline lanes and CLI are unaffected.
- **The connect bound is shared, not API-only.** `create_db_engine()` is what the
  CLI backfills and loaders use, so they inherit it. That is deliberate — an
  unbounded connect is no better in a backfill — but a very slow remote database
  would now fail at 5s where it previously waited.
- The probe applies its statement timeout only on a PostgreSQL bind. No other
  dialect is supported by the project, and the check is skipped rather than
  guessed at for anything else.
- The Alembic head is resolved once per process and cached (`lru_cache`), because
  migration scripts are static program files. The database state compared against
  it is read on every request and is never cached, as the contract requires.
