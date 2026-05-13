# NBA Data Platform

This repository is evolving from a Basketball Reference scraping prototype into
a maintainable NBA data platform.

The current codebase still contains the legacy prototype in `scrape_main.py`,
`scrap/`, `models/`, and `db_manager/`. Phase 1 adds the project harness,
configuration, cache, parser pattern, SQLAlchemy foundation, tests, and CI
without running live scraping.

## Current Phase

Phase 1: foundations, harness, rate limiter, HTML cache, parser pattern,
SQLAlchemy/Alembic foundation, and basic CI.

Planned later:

- read-only FastAPI under `/api/v1`;
- Next.js frontend;
- player rankings, OVR, and similarity metrics;
- progressive migration away from Peewee.

## Setup

Install `uv`, then run:

```bash
uv sync
```

Create a local environment file when needed:

```bash
cp .env.example .env
```

Start local PostgreSQL:

```bash
docker compose up -d postgres
```

Run tests and lint:

```bash
uv run pytest
uv run ruff check .
```

Run harness validation:

```bash
bash scripts/harness/init.sh
bash scripts/harness/validate.sh
```

## Legacy Scraper

The legacy scraper entrypoint is:

```bash
python scrape_main.py
```

Do not run this casually. It can contact Basketball Reference and write to the
legacy database. Live scraping requires explicit owner approval and must be
adapted to the central rate-limited client in a future phase.

## Responsible Scraping

Project defaults:

- 10 requests/minute against Basketball Reference;
- never exceed 20 requests/minute;
- minimum 6 seconds between requests;
- cache before network;
- no live scraping in tests or CI;
- respect `Retry-After`;
- stop or back off on HTTP 429.

## Key Docs

- `AGENTS.md`: project entrypoint for Codex and maintainers.
- `docs/ai/RULES.md`: coding and scraping rules.
- `docs/architecture/SYSTEM_DESIGN.md`: target architecture.
- `docs/domain/BUSINESS_RULES.md`: NBA domain decisions.
- `docs/roadmap/CURRENT_PHASE.md`: current scope.
- `tasks/feature-list.json`: structured task list.
- `progress/current.md`: current work memory.

## Owner Learning Path

Start with:

1. `AGENTS.md`
2. `docs/architecture/SYSTEM_DESIGN.md`
3. `docs/domain/BUSINESS_RULES.md`
4. `docs/roadmap/CHANGELOG_LEARNING.md`

These files explain what changed, why it changed, and what to review next.
