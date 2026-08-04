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
| `planning` | `plan-task`, `prepare-task` + the card's own domain areas | the card, plus the real code and tests for the area in question |

Anything in the card's `read:` list is loaded in addition to the above.

Planning cards carry `areas: [planning, <domain areas>]`. `prepare-task` drops
`planning` when it promotes the card to `tasks/backlog/`.

## On-demand only — never route by default

These are correct and authoritative, but too large to load speculatively. Open
them only when the task genuinely concerns their subject matter, and prefer `rg`
over a full read.

| File | Lines | Open when |
|---|---|---|
| `docs/architecture/IMPACT_MAP.md` | 190 | a task spans several areas, or its blast radius is unclear |
| `docs/architecture/OFFICIAL_STATS_SCHEMA.md` | 750 | changing `stats` schema, loaders, or stats validation |
| `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` | 96 | changing player-page parsing or normalization |
| `docs/validation/OFFLINE_DATABASE_PREPARATION.md` | 258 | running or changing the offline backfill path |
| `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md` | 95 | reviewing the completed team-season acquisition |
| `docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md` | 120 | performing an approved player-page acquisition |

`IMPACT_MAP.md` is an orientation map, not required reading. A small, isolated,
single-file task does not need it.

## Never startup context

`tasks/done/` · `tasks/planning/` when implementing · ADRs not relevant to the
current change. Use `rg` before opening any of them.

## Rules

- Do not invent a universal skill. Skills stay small and composable.
- Do not load every architecture file for every task.
- If a card's `areas` do not cover what you are about to change, that is a signal
  the card's scope is wrong — say so instead of silently widening it.
