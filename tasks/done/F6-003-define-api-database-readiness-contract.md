---
id: F6-003
title: Define the API database-readiness contract
areas:
  - api
  - database-read
  - documentation
priority: 90
depends_on:
  - F5-005
read:
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - src/nba_data/api/app.py
  - src/nba_data/api/routers/health.py
  - src/nba_data/api/dependencies.py
  - src/nba_data/config/settings.py
validation:
  - uv run python scripts/validate_tasks.py
  - uv run pytest -m "not integration and not live"
critical_actions: []
---

# Goal

Write the settled database-readiness contract into
`docs/architecture/API_CONTRACT.md` and `docs/architecture/API_ARCHITECTURE.md`,
with the same permanence the seasons resource already has, so the follow-up
implementation card (F6-005) can build the endpoint without inventing semantics.

Documentation only. This card ships no route, no setting, and no probe.

# Evidence and current state

- `GET /api/v1/health` is liveness only. `routers/health.py:8-14` returns
  `HealthResponse(status="ok")` and never touches a Session, a repository, or a
  network service. `API_ARCHITECTURE.md:32` and `API_CONTRACT.md:46` both state
  this deliberately, and `API_ARCHITECTURE.md:32` defers readiness to "a later
  explicit task" — this one.
- Nothing in the app connects eagerly. `lifespan` in `app.py:18-26` builds an
  Engine and a sessionmaker but opens no connection, and SQLAlchemy Sessions
  connect lazily, so `get_request_session` (`dependencies.py:9-13`) yields
  successfully even against a dead database. The failure surfaces on first
  statement execution, inside the route.
- A data route that cannot reach the database therefore falls through to
  `handle_unexpected_error` (`app.py:29-32`) and returns
  `{"detail": "Internal Server Error"}` with status 500. That is
  indistinguishable from a genuine bug and is not a readiness signal.
- `API_CONTRACT.md:32-34` fixes the error contract: bodies use `detail`, the
  500 body is a fixed string that never varies with the cause, and no body ever
  exposes SQL, credentials, or local paths. Any readiness contract must fit
  inside that rule rather than around it.
- The PostgreSQL integration lane already established how migration state is
  verified: `tests/integration/test_api_postgres.py:125-145` reads
  `SELECT version_num FROM alembic_version` and compares it against
  `ScriptDirectory.from_config(...).get_heads()`, failing loudly when the schema
  is behind. `alembic` is a runtime dependency (`pyproject.toml:7`), not a dev
  one, so a runtime probe may legitimately resolve heads the same way.
- `Settings` (`config/settings.py`) has no API-side timeout. `scraper_timeout_seconds`
  exists but belongs to acquisition and must not be reused here.
- `tests/unit/test_api_foundation.py` asserts every OpenAPI path begins with
  `/api/v1/`, so the chosen route must live under the version prefix.

# Human decisions or resources

- [x] **All five decisions below were settled by the user on 2026-08-12.** No
      decision remains open; the contract text is fully determined.
- [x] **Route and methods.** `GET /api/v1/health/ready`, GET only. It stays in
      the existing health router so both operational signals sit in one
      namespace, and it satisfies the `/api/v1/` prefix rule.
- [x] **Meaning of readiness.** Connection *and* migrated schema *and* the
      required tables the API reads. A reachable but un-migrated or empty
      database must report not-ready rather than reporting ready and then
      failing every data route with a 500.
- [x] **Status codes and bodies.** 200 for ready; 503 for every not-ready case,
      using the existing `detail` field with fixed strings that do not vary with
      the underlying exception. Three distinguishable causes, no internals
      leaked. See "Acceptance criteria" for the exact wording.
- [x] **Probe timing.** Per request, bounded by a configurable timeout. Startup
      stays non-blocking so the app still boots and reports honestly when the
      database is down. No cached verdict — a database that dies after boot must
      stop reporting ready.
- [x] **Proving the contract.** Offline unit tests with dependency overrides and
      a stubbed probe, plus the existing PostgreSQL integration lane in
      `tests/integration/test_api_postgres.py`. No Basketball Reference contact
      at any point.

# Acceptance criteria

- `docs/architecture/API_CONTRACT.md` gains a **Readiness** section, adjacent to
  the existing **Health** section, stating:
  - `GET /api/v1/health/ready` is the readiness route, GET only;
  - the ready body is `{"status": "ready"}` with status 200;
  - the three not-ready cases, each 503 with a fixed `detail` string:
    `"Database unavailable"` (connection failed), `"Database readiness check
    timed out"` (probe exceeded its bound), `"Database schema not ready"`
    (connected, but the Alembic revision is not at head or a required table is
    missing);
  - that the `detail` strings are fixed and never carry the underlying
    exception, driver message, SQL, credentials, or paths;
  - that readiness is evaluated per request and never cached.
- The **Errors** section of `API_CONTRACT.md` is extended to admit 503 as a
  contract status code for readiness, without weakening the existing 400 / 404 /
  422 / 500 rules or the fixed-500-body guarantee.
- `API_CONTRACT.md` states explicitly that `GET /api/v1/health` remains liveness
  only and is unchanged by this contract — the two signals never merge.
- `docs/architecture/API_ARCHITECTURE.md` replaces "Database readiness is
  separate and requires a later explicit task" with the settled runtime
  boundaries:
  - the probe owns its own bounded execution and never inherits an unbounded
    request lifetime;
  - the probe uses the ordinary per-request Session dependency and does not open
    its own Engine, which would violate the one-Engine-per-app rule;
  - probe failures are caught inside the readiness path and converted to 503;
    they must not escape to `handle_unexpected_error` and become a 500;
  - the failure is logged server-side with its cause, exactly as the 500 handler
    already does;
  - startup remains non-blocking: a database that is down at boot does not
    prevent the app from starting.
- The naming and default of the readiness timeout setting are stated in
  `API_ARCHITECTURE.md` (`api_readiness_timeout_seconds`, default `2.0`,
  must be `> 0`) so F6-005 implements the agreed name rather than choosing one.
- The documents name which tables count as "required": those backing the
  currently served data routes, `core.teams` and `core.seasons`, and state that
  the list grows with each new data resource.
- No file under `src/` or `tests/` is modified by this card.
- `uv run python scripts/validate_tasks.py` passes.

# Scope

`docs/architecture/API_CONTRACT.md` and `docs/architecture/API_ARCHITECTURE.md`
only.

# Out of scope

Implementing the readiness endpoint, adding the setting to `Settings`, writing
the probe, changing `GET /api/v1/health`, changing migrations, changing any
existing route or test, and contacting external services. All of that is F6-005.

# Impact

Contract-level. Fixes the public shape of a route that does not yet exist, adds
503 to the documented status codes, and constrains how F6-005 may implement the
probe. No runtime behavior changes in this card. Downstream, F6-005 will touch
`src/nba_data/api/routers/health.py`, `schemas/health.py`, `services/`,
`config/settings.py`, `tests/unit/`, and `tests/integration/test_api_postgres.py`.

# Implementation notes

Keep liveness and readiness as separate signals throughout. Do not make
`/health` depend on PostgreSQL merely to obtain a green check.

Write the 503 wording so it is honest under the existing error rule: the point
of three fixed strings is that an operator can tell "database is down" from
"database is up but un-migrated" without the body ever varying with the
exception text. If a fourth cause is ever needed, it gets its own fixed string;
the strings never interpolate.

State the per-request decision plainly enough that a future reader does not
"optimize" it into a cached verdict. A cached ready is worse than no readiness
route, because it is confidently wrong.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — the settled public readiness contract.
- `docs/architecture/API_ARCHITECTURE.md` — probe ownership, runtime boundaries,
  the timeout setting name and default, and the startup guarantee.

# Review evidence

## Automated validation

- Command: `uv run python scripts/validate_tasks.py`
- Result: `Task validation passed.`

- Command: `uv run pytest -m "not integration and not live"`
- Result: `387 passed, 2 deselected, 7 warnings in 11.31s`. The two deselected
  are the PostgreSQL integration tests; the seven warnings are pre-existing
  third-party deprecations (Starlette `TestClient`/httpx, peewee `to_field`) and
  are unrelated to this card.

- Command: `git status --short -- src tests`
- Result: empty — this card changed no source or test file, as its scope
  requires. The full diff is two documents plus the task cards.

## Manual happy path

1. Open `docs/architecture/API_CONTRACT.md` and read the **Health** and
   **Readiness** sections in order. Confirm the readiness route is
   `GET /api/v1/health/ready`, the ready body is `{"status": "ready"}` at 200,
   and the three 503 causes each have one fixed `detail` string.
2. Read the **Errors** section above them. Confirm 503 is admitted, confined to
   the readiness route, and that the 400/404/422/500 rules and the fixed-500-body
   guarantee are unchanged from before.
3. Open `docs/architecture/API_ARCHITECTURE.md` and read **Health and
   readiness**. Confirm it now states startup non-blocking, one Session from the
   ordinary dependency, the bounded probe with
   `api_readiness_timeout_seconds` default `2.0`, self-converted failures, and
   service/router layering — and that the old sentence deferring readiness to
   "a later explicit task" is gone.
4. Open `tasks/backlog/F6-005-implement-api-database-readiness-endpoint.md` and
   check each acceptance criterion against the contract text. Every one should
   be answerable from the two documents without a further decision.

Expected result: an implementer can build the endpoint from the documents alone,
with no semantic question left open.

## Manual sad path

1. Try to satisfy the contract by making `GET /api/v1/health` return the
   database verdict. The **Readiness and liveness never merge** paragraph and the
   Health section forbid it explicitly.
2. Try to cache the readiness verdict at startup for speed. The **evaluated per
   request and never cached** paragraph rejects it and gives the reason.
3. Try to include the SQLAlchemy error text in the 503 body to aid debugging.
   The fixed-strings paragraph and the Errors section both forbid it, and point
   to server-side logging instead.
4. Try to let a database error propagate to the catch-all handler in
   `app.py:41` and call the resulting 500 acceptable. The **probe converts its
   own failures** paragraph names this as a defect, not a fallback.

Expected result: each shortcut is refused by a specific, quotable clause rather
than by taste, so the contract holds up under review pressure.

## Known limitations

- The contract is written but not enforced by any test until F6-005 implements
  the endpoint. Nothing today fails if the documents and the code disagree,
  because the route does not exist yet.
- `.agents/skills/api-fastapi/SKILL.md` still says "Readiness is a separate
  future task." That remains true while F6-005 is unstarted, so it was left
  alone; F6-005 should update that line when it lands.
- The required-tables list (`core.teams`, `core.seasons`) is maintained by hand.
  Adding a data resource without adding its table leaves a gap the readiness
  route will not catch.
