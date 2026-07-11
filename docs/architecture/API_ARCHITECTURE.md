# API architecture

## Scope: Phase 5

Phase 5 is a read-only, GET-only FastAPI surface under `/api/v1`. It has no authentication, frontend, scraping, backfills, writes, migrations, rankings, OVR, similarity, ML, or other generated analytics.

## Runtime model

FastAPI uses synchronous SQLAlchemy. Database endpoints normally use `def`; no async DB stack, `AsyncSession`, `asyncpg`, or `create_async_engine` is introduced without a dedicated task. Each app instance owns one long-lived Engine and one sessionmaker through lifespan; each request receives one Session, which is then closed. Never create an Engine per request or retain a global Session.

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

## Health

`GET /api/v1/health` is liveness only: it confirms the process without checking the database, creating a Session, invoking a repository, or using network services. Database readiness is separate and requires a later explicit task.

## Query repositories

API reads use dedicated repositories in `db/repositories/queries/`, not `CoreRepository`, which has write-capable `get_or_create` methods. Query repositories are read-only, use deterministic ordering, and never mutate their Session.

## Mapping

ORM entities are not public contracts. Responses use explicit Pydantic schemas and safe mapping: explicit service mapping for complex data, or `from_attributes=True` only for fully loaded simple entities. Required relationships are loaded before mapping to prevent lazy loading and N+1 queries.

## Testing strategy

HTTP tests use offline `TestClient`, local fixtures, and dependency overrides. App foundation tests do not need PostgreSQL; real DB integration is a future, separate layer.
