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

## Loader Invariants

The pipeline boundary is fixed:

```text
cached HTML -> pure parser -> normalizer -> validator -> idempotent loader
```

- Cached HTML is the raw source of truth for repeatable parsing.
- Parsers receive HTML strings and touch neither network nor database.
- Normalizers convert parser rows into canonical records with explicit source
  metadata.
- Validators check row shape, required identifiers, duplicates, and domain rules
  before any database write.
- Loaders write only validated records and must be safe to rerun: check natural
  keys before writing, use portable select-then-insert/update logic, and leave
  transaction control to the caller.

## Planned Direction

Work after the read-only API, in order:

**Web frontend** — consumes the API only. It must never query the database
directly or trigger scraping. See ADR 0008 for the stack decision.

**Generated metrics, rankings, and OVR** — stored in the `features` schema,
never mixed into `raw`, `core`, or official `stats` tables. Formula versions are
recorded, assumptions and limitations documented, and metric generation must be
leakage-safe and must never scrape live.

Concrete work is tracked as cards in `tasks/backlog/`, not as phase documents.
