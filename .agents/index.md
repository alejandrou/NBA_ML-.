# Skill and document router

Map the active card's `areas` to skills and durable context. Combined areas load
the **union** — read each file once.

| Area | Skills | Durable context |
|---|---|---|
| `api` | `api-fastapi`, `testing` | `docs/architecture/API_ARCHITECTURE.md`, `docs/architecture/API_CONTRACT.md` |
| `database-read` | `db-readonly`, `testing` | `src/nba_data/db/models/core.py` |
| `database-schema` | `db-schema`, `testing` | `docs/architecture/SYSTEM_DESIGN.md`, `alembic/` conventions |
| `scraping` | `scraping-pipeline`, `data-quality`, `testing` | `docs/architecture/SYSTEM_DESIGN.md`, `docs/domain/BUSINESS_RULES.md` |
| `data-quality` | `data-quality`, `testing` | `docs/domain/BUSINESS_RULES.md` |
| `testing` | `testing` | — |
| `review` | `review` + the card's own domain areas | the card and the current diff |
| `documentation` | — | only the durable docs the change actually affects |

Anything in the card's `read:` list is loaded in addition to the above.

## On-demand only — never route by default

These are correct and authoritative, but too large to load speculatively. Open
them only when the task genuinely concerns their subject matter, and prefer `rg`
over a full read.

| File | Lines | Open when |
|---|---|---|
| `docs/architecture/OFFICIAL_STATS_SCHEMA.md` | 750 | changing `stats` schema, loaders, or stats validation |
| `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` | 96 | changing player-page parsing or normalization |
| `docs/validation/OFFLINE_DATABASE_PREPARATION.md` | 258 | running or changing the offline backfill path |
| `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md` | 95 | performing an approved live acquisition |

## Never startup context

`tasks/done/` · `specs/` · ADRs not relevant to the current change. Use `rg`
before opening any of them.

## Rules

- Do not invent a universal skill. Skills stay small and composable.
- Do not load every architecture file for every task.
- If a card's `areas` do not cover what you are about to change, that is a signal
  the card's scope is wrong — say so instead of silently widening it.
