# API architecture

## Scope: Phase 5

Phase 5 is a read-only, GET-only FastAPI surface under `/api/v1`. It has no authentication, frontend, scraping, backfills, writes, migrations, rankings, OVR, similarity, ML, or other generated analytics.

## Runtime model

FastAPI uses synchronous SQLAlchemy. Database endpoints normally use `def`; no async DB stack, `AsyncSession`, `asyncpg`, or `create_async_engine` is introduced without a dedicated task. Each app instance owns one long-lived Engine and one sessionmaker through lifespan; each request receives one Session, which is then closed. Never create an Engine per request or retain a global Session.

`nba-data serve` is the supported way to run the app: it calls `uvicorn.run("nba_data.api:create_app", factory=True, ...)`, binding `127.0.0.1` by default. The CLI opens no database connection itself — the Engine is still built by `lifespan`.

## Package layout

```text
src/nba_data/api/
  __init__.py
  app.py
  dependencies.py
  routers/
  schemas/
  services/
src/nba_data/db/repositories/queries/
```

`app.py` owns `create_app()`, lifespan, configuration, and router registration. `dependencies.py` supplies typed application resources. Routers translate HTTP and validate input; services orchestrate use cases; query repositories execute SQLAlchemy reads; schemas define Pydantic public contracts.

## Dependency direction

API may depend on DB query repositories, but repositories never depend on API or FastAPI. Routers may import services, schemas, and dependencies; services may import repositories and schemas; repositories may import Session and ORM models. Schemas never import Sessions, repositories, or scraping. API code never imports loaders, acquisition code, or scraping.

## Health and readiness

`GET /api/v1/health` is liveness only: it confirms the process without checking the database, creating a Session, invoking a repository, or using network services.

`GET /api/v1/health/ready` is the separate readiness signal. `API_CONTRACT.md` fixes its public shape — route, status codes, bodies, and the per-request rule. The runtime boundaries below are binding on any implementation of it.

**Startup stays non-blocking.** Lifespan builds the Engine and the sessionmaker but opens no connection, and SQLAlchemy Sessions connect lazily. An app whose database is unreachable therefore still starts, serves liveness, and reports 503 from readiness. Readiness must not be moved into lifespan, and lifespan must not be made to fail on an unreachable database — an app that refuses to boot cannot tell anyone why.

**The probe owns one Session, from the ordinary dependency.** It uses the same per-request Session dependency every data route uses. It never calls `create_db_engine()` itself; a second Engine would break the one-Engine-per-app rule above and leak a connection pool per request.

**The probe is bounded.** It carries its own time bound and never inherits an unbounded request lifetime, so a database that accepts a connection and then stops answering produces a 503 rather than a hung worker. The bound is configuration, not a literal: `api_readiness_timeout_seconds`, default `2.0`, constrained to `> 0`. It is distinct from `scraper_timeout_seconds`, which belongs to acquisition and must not be reused here.

**The probe converts its own failures.** Because `create_app()` registers a catch-all `Exception` handler that returns 500, any database error escaping the readiness path would surface as a 500 and violate the contract. The readiness path therefore catches its failures itself and maps them to 503, and the cause is logged server-side exactly as the 500 handler logs it. Escaping to the generic handler is a defect, not a fallback.

**Layering is unchanged.** The check is a service; the router only translates its outcome into a status code and a fixed body. The service returns distinct outcomes for unreachable, timed-out, and schema-not-ready so the router never inspects exception text to decide which body to send.

## Query repositories

API reads use dedicated repositories in `db/repositories/queries/`, not `CoreRepository`, which has write-capable `get_or_create` methods. Query repositories are read-only, use deterministic ordering, and never mutate their Session.

## Mapping

ORM entities are not public contracts. Responses use explicit Pydantic schemas and safe mapping: explicit service mapping for complex data, or `from_attributes=True` only for fully loaded simple entities. Required relationships are loaded before mapping to prevent lazy loading and N+1 queries.

## Testing strategy

HTTP tests use offline `TestClient`, local fixtures, and dependency overrides. App foundation tests do not need PostgreSQL; real DB integration is a future, separate layer.
