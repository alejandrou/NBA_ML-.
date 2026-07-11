---
name: api-fastapi
description: Use for designing, implementing, or reviewing the approved read-only FastAPI surface, including app factories, routers, schemas, dependencies, HTTP contracts, pagination, errors, OpenAPI, and TestClient tests; do not use for scraping, writes, migrations, frontend, or generated metrics.
---

## Use when

Designing, implementing, or reviewing an approved read-only FastAPI task.

## Do not use when

The task concerns scraping, writes, migrations, frontend, authentication, or generated metrics.

## Required inputs

Read the active card, API architecture and contract, and the references relevant to the requested layer.

## Approved architecture

Use `/api/v1` and `create_app()` with `app.py`, `dependencies.py`, `routers/`, `schemas/`, and `services/` under `src/nba_data/api/`; read-only query repositories live in `src/nba_data/db/repositories/queries/`. Routers translate HTTP, services compose use cases, repositories run SQLAlchemy queries, and schemas define public contracts.

## Workflow

Confirm the approved scope, define explicit schemas and contracts, implement the smallest affected layers, then add offline `TestClient` coverage.

## Required patterns

- Initial HTTP scope is GET-only under `/api/v1`: no auth, frontend, scraping, backfills, data changes, or migrations.
- Keep SQLAlchemy synchronous: DB endpoints normally use `def`; never call blocking SQLAlchemy from `async def`, or introduce `AsyncSession`, `asyncpg`, or `create_async_engine`.
- Use an app factory and lifespan: one Engine and one sessionmaker per app, a Session per request, and Engine disposal at shutdown. Never create an Engine per request, query at import time, or keep a global Session.
- Dependencies are small, typed, closed reliably, overrideable in tests, and never commit or hide writes.
- Routers declare `response_model`, call services, and translate application errors; they contain neither SQLAlchemy queries nor heavy business logic. Services do not depend on `Request`/`Response`, run SQL directly, serialize arbitrary ORM objects, or import scraping. Repositories contain read-only SQLAlchemy only and do not import FastAPI or create HTTP responses.
- Health is liveness only: `GET /api/v1/health` returns process health without DB Sessions, repositories, network calls, or DB checks. Readiness is a separate future task.
- Use explicit Pydantic schemas and public `snake_case` fields. Do not return ORM models or `__dict__`; declare nullability and expose only approved fields. Use explicit service mapping for complex responses, or `ConfigDict(from_attributes=True)` only for fully loaded simple entities. Prevent lazy loading and N+1 queries; load required relationships deliberately.
- Keep FastAPI/Pydantic request validation as 422, return 404 for missing resources, 400 for syntactically valid but semantically incompatible input, and 500 for unexpected failures. Do not leak SQL errors or replace default validation handling without an explicit contract decision.
- Paginate with `page=1`, `page_size=50`, minimums of 1, and maximum `page_size=100`. `total` is filtered pre-pagination count; empty valid pages return 200 with `items: []`; every paginated query has deterministic `ORDER BY` plus a stable tie-breaker.
- Register only approved versioned routes, tags, concise summaries, and public schemas in OpenAPI; do not customize operation IDs unless needed.

## Forbidden actions

No POST, PUT, PATCH, DELETE, writes, reuse of write-capable repositories, scraping, backfills, migrations without an explicit card, or unapproved endpoints.

## Validation

Run the task-card checks. Use `TestClient` as a context manager when lifespan applies, clear overrides, and keep HTTP tests offline and deterministic.

## Expected output

A narrow, contract-compliant API change with isolated resources, explicit contracts, and focused tests.

## References

Load `references/architecture.md`, `session-lifecycle.md`, `schemas-and-contracts.md`, `errors-and-pagination.md`, and `testing.md` as needed.
