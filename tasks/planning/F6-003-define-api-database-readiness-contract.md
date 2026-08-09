---
id: F6-003
title: Define the API database-readiness contract
areas:
  - planning
  - api
  - database-read
  - testing
priority: 90
depends_on:
  - F5-005
read:
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - src/nba_data/api/app.py
  - src/nba_data/api/dependencies.py
  - src/nba_data/config/settings.py
validation: []
critical_actions: []
---

# Goal

Resolve what database readiness means for the read-only API before adding a
readiness endpoint or changing the liveness health route.

# Evidence and current state

- `GET /api/v1/health` is intentionally liveness-only and does not open a
  database session.
- `docs/architecture/API_ARCHITECTURE.md` says database readiness is separate
  and requires a later explicit task, but no route, status code, probe query, or
  failure contract is defined.
- The current app returns the generic unexpected-error response when a data
  route cannot reach the database; that is not a readiness signal.

# Human decisions or resources

- [ ] Choose the public route and allowed methods for readiness.
- [ ] Decide whether readiness means only a successful connection/probe or also
      a migrated schema and required tables.
- [ ] Define ready, unavailable, timeout, and migration/schema-failure status
      codes and JSON bodies without weakening the existing error contract.
- [ ] Decide whether the probe runs per request, during startup, or both, and
      how its timeout and server-side logging are bounded.
- [ ] Decide which local/CI checks and manual operational steps prove the
      contract without contacting Basketball Reference.

# Acceptance criteria

Not final — this card is not ready to start. Draft direction:

- `docs/architecture/API_CONTRACT.md` and `API_ARCHITECTURE.md` state the
  readiness route, probe semantics, response bodies, and relationship to
  liveness.
- A follow-up implementation card can name focused unit, API, and PostgreSQL
  integration validation commands without inventing missing semantics.

# Scope

Contract and operational research around `src/nba_data/api/`, database session
creation, and the API architecture/contract documents.

# Out of scope

Implementing the readiness endpoint, changing `GET /api/v1/health`, changing
database migrations, or contacting external services.

# Impact

Potentially affects API routes, error handling, monitoring expectations, and
the PostgreSQL integration lane. No current runtime behavior changes in this
planning task.

# Implementation notes

Keep liveness and readiness as separate signals. Do not make health depend on
PostgreSQL merely to obtain a green check, and do not turn an operational
decision into an undocumented implementation default.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — record the settled public readiness
  contract in the later implementation card.
- `docs/architecture/API_ARCHITECTURE.md` — record probe ownership and runtime
  boundaries.

# Review evidence

## Automated validation

- Command:
- Result:

## Manual happy path

1. Review the current health behavior and API error contract.
2. Answer the readiness questions above.
3. Confirm the resulting contract can be tested offline and against the local
   disposable database.

Expected result: one unambiguous readiness contract exists for preparation.

## Manual sad path

1. Stop the local PostgreSQL service.
2. Compare the current liveness response with a data-route failure.
3. Record which distinction the future readiness route must expose.

Expected result: the decision captures unavailable-database behavior without
changing the current liveness guarantee.

## Known limitations

- No implementation or runtime probe is added until the decisions are resolved.
