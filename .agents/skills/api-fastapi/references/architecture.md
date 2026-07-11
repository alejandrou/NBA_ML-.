# API reference: architecture

Use `src/nba_data/api/{app.py,dependencies.py,routers/,schemas/,services/}` and read-only repositories in `src/nba_data/db/repositories/queries/`. `create_app()` owns configuration, lifespan, and versioned router registration. Dependencies expose application resources.

```text
HTTP request
  -> router
  -> service
  -> query repository
  -> SQLAlchemy Session
  -> database
```

```text
ORM entity or typed projection
  -> service mapping
  -> Pydantic response schema
  -> router
  -> JSON response
```

Routers may import services, schemas, and dependencies. Services may import repositories and schemas. Repositories may import Session and ORM models, but never FastAPI. Schemas may not import Session, repositories, or scraping. API code must not import loaders or acquisition/scraping code. Keep SQLAlchemy synchronous; database endpoints normally use `def`.
