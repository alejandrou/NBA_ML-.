# System Design

## Target Architecture

```text
Scraper batch/job
  -> raw HTML cache
  -> parsers
  -> normalizers
  -> validators
  -> idempotent loaders
  -> PostgreSQL
  -> features/metrics
  -> FastAPI
  -> Next.js
```

## Target Python Layout

```text
src/nba_data/
  config/
  scraping/
    client.py
    cache.py
    parsers/
    normalizers/
    loaders/
  db/
    base.py
    session.py
    models/
    repositories/
  features/
  validation/
  cli/
```

Future app split:

```text
apps/
  scraper/
  api/
  web/
```

## Responsibilities

- Scraper jobs plan URLs and orchestrate work.
- The HTTP client is the only place for real Basketball Reference requests.
- Cache stores raw HTML as `.html.gz`.
- Parsers are pure functions from HTML to structured data.
- Normalizers convert raw parsed rows into canonical shapes.
- Validators check row counts, keys, ranges, and historical missing metrics.
- Loaders write idempotently to PostgreSQL.
- API reads processed data only and never scrapes live.
- Frontend consumes the API, not the database directly.

## Phase 1 Scope

Phase 1 adds project harness, settings, local Postgres compose, rate-limited
client, HTML cache, parser pattern, SQLAlchemy/Alembic foundation, tests, and CI.

## Future Scope

Future phases adapt legacy scrapers, expand parsers, add idempotent loaders,
migrate Peewee progressively, build a read-only API, and later build the web UI
and generated metrics.
