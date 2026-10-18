---
id: F6-018
title: Record why the API keeps the shared database role
track: app
areas:
  - documentation
  - database-read
priority: 41
depends_on: []
read:
  - docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md
  - docs/architecture/API_ARCHITECTURE.md
  - src/nba_data/config/settings.py
  - src/nba_data/db/session.py
  - src/nba_data/api/app.py
  - src/nba_data/api/dependencies.py
  - src/nba_data/api/services/readiness.py
  - docker-compose.yml
validation:
  - uv run pytest tests/unit/test_api_foundation.py tests/unit/test_api_session_lifecycle.py
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. No role is created and no privilege changes on any database.
---

# Goal

Close the privilege half of finding 2 of the 2026-09-08 audit with a decision:
the read-only API keeps connecting through `DATABASE_URL` as the shared `nba`
role for now. Record why in ADR 0021, with the conditions that reopen it, so
the next audit does not re-raise the same finding as open work.

# Evidence and current state

- The audit found one non-system role, `nba`, a superuser; every component
  connects as it through one setting (`settings.py`, `db/session.py`,
  `api/app.py`). It found no write path in the API.
- The API's read-only guarantee is enforced by code at three layers: reads only
  through `db/repositories/queries/` (`API_ARCHITECTURE.md`), a request-scoped
  Session that never commits (`api/dependencies.py`), and a GET-only surface.
- The network half is closed: F6-016 binds the database to
  `127.0.0.1` by default (`docker-compose.yml`).
- The platform is local and single-owner (`docs/ml/PREDICTOR_PLAN.md` §5:
  "Execution: local").
- Cost of a separate role: a provisioning step per environment, a second URL,
  a CI lane with two roles, and a new failure mode — every table a migration
  adds needs a grant or the API 503s/500s. The coming game and `ml` tables
  (F8-002, F8-010) would each hit it.

# Human decisions or resources

- [x] **Separation is declined for now** (decided 2026-10-18): it adds
      operational cost against a guarantee the code already provides, on a
      loopback-only, single-owner database. Not a fix deferred — a recorded
      decision.
- [x] **Reopen conditions**, written in the ADR: the database or the API becomes
      reachable beyond loopback; a second person or service connects; the API
      gains any write route; or the platform is deployed off the owner's
      machine. Any one of them makes this card's original design (a SELECT-only
      role with `ALTER DEFAULT PRIVILEGES`, readiness proven as that role, CI
      testing the grants) the next step.
- [x] **Transport (SSL) stays out of scope** while the binding is loopback; it is
      a reopen condition, not a separate task.

# Acceptance criteria

- `docs/decisions/0021-keep-the-shared-database-role-for-the-api.md` (status
  Accepted): context (audit finding 2, the three code layers, F6-016), the
  decision, the reopen conditions above, the rejected alternative with its
  costs, and the design to follow when it reopens.
- `PROJECT_DATABASE_AUDIT_2026-09-08.md` finding 2 gains one line pointing at
  F6-016 (network) and ADR 0021 (privilege).
- `API_ARCHITECTURE.md` states in one sentence that the read-only guarantee is
  code-level by decision (ADR 0021).
- No code, setting, role, or grant changes.

# Scope

The new ADR, the audit record, and `API_ARCHITECTURE.md`.

# Out of scope

Creating any role, changing any credential, `.env`, CI, the app factory, or
settings.

# Impact

- Documentation only.

# Cross-track impact

- None.

# Implementation notes

- Check `docs/decisions/` for the next free number first; if 0021 is taken, use
  the next one and update this card's references.

# Durable knowledge updates

- `docs/decisions/0021-…`, the audit record, `API_ARCHITECTURE.md`.

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
