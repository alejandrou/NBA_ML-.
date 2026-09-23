# Skill and document router

Map the active card's `areas` to skills and durable context. Combined areas load
the **union** — read each file once.

| Area | Track | Skills | Durable context |
|---|---|---|---|
| `api` | `app` | `api-fastapi`, `testing` | `docs/architecture/API_ARCHITECTURE.md`, `docs/architecture/API_CONTRACT.md` |
| `web` | `app` | — (a skill is pending F7-001) | `docs/decisions/0006-separate-scraper-api-web.md`, `docs/decisions/0008-use-nextjs-for-future-frontend.md` |
| `database-read` | any | `db-readonly`, `testing` | `src/nba_data/db/models/core.py` |
| `database-schema` | `data` | `db-schema`, `testing` | `docs/architecture/SYSTEM_DESIGN.md`, `alembic/` conventions |
| `scraping` | `data` | `scraping-pipeline`, `data-quality`, `testing` | `docs/architecture/SYSTEM_DESIGN.md`, `docs/domain/BUSINESS_RULES.md` |
| `data-quality` | `data` | `data-quality`, `testing` | `docs/domain/BUSINESS_RULES.md` |
| `ml` | `data` | `testing` | `docs/ml/PREDICTOR_PLAN.md` |
| `testing` | any | `testing` | — |
| `review` | any | `review` + the card's own domain areas | the card and the current diff |
| `documentation` | any | — | only the durable docs the change actually affects |
| `planning` | any | `plan-task`, `prepare-task` + the card's own domain areas | the card, plus the real code and tests for the area in question |

Anything in the card's `read:` list is loaded in addition to the above.

A `data` or `app` card uses only its own track's areas and the `any` ones once it
leaves `planning/`; a `shared` card may use every area (ADR 0018,
`scripts/validate_tasks.py`).

Planning cards carry `areas: [planning, <domain areas>]`. `prepare-task` drops
`planning` when it promotes the card to `tasks/backlog/`.

## Routed by command, not by area

| Command | Skill |
|---|---|
| `Park the current task.` · `Resume <TASK-ID>.` | `park-resume` |

The other short commands and their skills are listed in `AGENTS.md`.

## On-demand only — never route by default

These are correct and authoritative, but too large to load speculatively. Open
them only when the task genuinely concerns their subject matter, and prefer `rg`
over a full read.

| File | Lines | Open when |
|---|---|---|
| `docs/architecture/IMPACT_MAP.md` | 190 | a task spans several areas, or its blast radius is unclear |
| `docs/architecture/OFFICIAL_STATS_SCHEMA.md` | 750 | changing `stats` schema, loaders, or stats validation |
| `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` | 96 | changing player-page parsing or normalization |
| `docs/validation/OFFLINE_DATABASE_PREPARATION.md` | 647 | running or changing the offline backfill path |
| `docs/validation/MIGRATION_HEAD_HANDOVER.md` | 190 | applying a migration to the persistent `nba` database, or changing the preflight that gates it |
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
