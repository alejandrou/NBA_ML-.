# NBA Data Platform

This repository is evolving from a Basketball Reference scraping prototype into
a maintainable NBA data platform.

The current codebase still contains the legacy prototype in `scrape_main.py`,
`scrap/`, `models/`, and `db_manager/`. The new platform foundation adds the
project harness, configuration, cache, parser pattern, SQLAlchemy foundation,
tests, CI, and a reviewed scraper/cache integration path without running
unapproved live scraping.

## Roadmap

The project roadmap and phase gates are in
[`docs/roadmap/ROADMAP.md`](docs/roadmap/ROADMAP.md). It is the only operational
source for phase status; this README intentionally does not track current work.

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

- `AGENTS.md`: project entrypoint and stable repository guardrails.
- `tasks/CURRENT.md`: pointer to the single active executable task card.
- `docs/architecture/SYSTEM_DESIGN.md`: target architecture.
- `docs/domain/BUSINESS_RULES.md`: NBA domain decisions.
- `docs/roadmap/ROADMAP.md`: phases and transition gates.
- `.agents/skills/`: reusable task-type workflows.

## Working with Codex

Start a new session with `Implement the current task.` or `Review the current
task without modifying code.` Codex will load, in order:

1. `AGENTS.md`
2. `tasks/CURRENT.md`
3. The referenced task card, its skills, and its `must_read` files.

Historical feature specifications remain under `specs/features/` but are not
startup material.
