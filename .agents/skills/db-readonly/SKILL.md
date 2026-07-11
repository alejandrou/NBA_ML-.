---
name: db-readonly
description: Use for designing, implementing, or reviewing SQLAlchemy query repositories and request-scoped read-only database access; do not use for schema changes, migrations, loaders, backfills, session mutations, or write repositories.
---

## Use when

Creating or reviewing application read queries and request-scoped SQLAlchemy access.

## Do not use when

Changing schemas, migrations, loaders, backfills, mutations, or write repositories.

## Read-only boundary

Never use `CoreRepository` from the API or any repository exposing `get_or_create`. Create dedicated query repositories under `src/nba_data/db/repositories/queries/` (initially `teams.py` and `seasons.py`, unless the real structure justifies another name). Read-only application access does not make ORM models immutable; the boundary relies on using only query repositories and never mutating a Session.

## Session rules

Receive the caller-owned Session; do not close it, return it, share it across requests, or commit. Request lifecycle owns creation and closure.

## Query repository rules

Use explicit names such as `list_teams`, `get_team`, `count_teams`, `list_seasons`, `get_season`, and `count_seasons`. Repositories use `select`, typed filters, stable ordering, executed results (`.scalars()` or `.scalar_one_or_none()` where appropriate), and loaded entities or typed projections. Avoid N+1 queries and do not return unexecuted queries.

## Query patterns

Apply filtering before counting and pagination. Use deterministic ordering with a stable tie-breaker. Load only relationships actually needed by the public response.

## Forbidden actions

Do not call `session.add`, `add_all`, `flush`, `commit`, `delete`, or `merge`; execute INSERT, UPDATE, DELETE, DDL, migrations, or scraping; manage `HTTPException`; or import FastAPI.

## Testing

Support local-Session tests and repository fakes. Use deterministic fixtures and verify empty, filtered, ordered, and paginated results without a production/shared database.

## Validation

Run the active task card's focused tests and declared checks.
