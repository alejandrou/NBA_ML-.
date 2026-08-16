---
id: F7-001
title: Define the frontend MVP scope and contract
areas:
  - planning
priority: 110
depends_on:
  - F6-004
read:
  - docs/decisions/0008-use-nextjs-for-future-frontend.md
  - docs/decisions/0006-separate-scraper-api-web.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - tasks/planning/F6-004-define-public-player-stats-api-contract.md
  - tasks/done/F6-003-define-api-database-readiness-contract.md
  - src/nba_data/api/app.py
validation: []
critical_actions: []
---

# Goal

Define what the first frontend delivers, how it is built, and exactly which
pages and data it covers, so a later implementation card has no ambiguity to
resolve. The first pass is deliberately minimal: read-only views over whatever
the API already exposes, not the full players/rankings/comparisons product
described as a later phase in ADR 0008.

# Evidence and current state

- `src/nba_data/api/routers/` currently exposes only `health`, `teams`, and
  `seasons`. There are no player or statistics routes yet; those are gated on
  `F6-004`, which is itself still in `tasks/planning/` with open decisions.
- `docs/architecture/API_ARCHITECTURE.md` states Phase 5 explicitly excludes
  frontend, authentication, and generated analytics.
- `src/nba_data/api/app.py:35-49` (`create_app()`) registers no
  `CORSMiddleware` or any other middleware. A browser-based frontend on a
  different origin (e.g. a Next.js dev server) would currently be blocked by
  the browser's CORS policy.
- `docs/decisions/0008-use-nextjs-for-future-frontend.md` commits to Next.js,
  TypeScript, Tailwind, and shadcn/ui "in a future phase," for a UI covering
  players, rankings, and comparisons; it explicitly defers all of that.
- `docs/decisions/0006-separate-scraper-api-web.md` requires the frontend to
  consume API data only — it may never query the database directly.
- No frontend directory, `package.json`, or `.agents` skill exists anywhere in
  the repository yet. `.agents/index.md` has no `frontend`/`web` area entry.
- A DB-readiness endpoint (distinct from the existing liveness-only
  `/api/v1/health`) was delivered by `F6-003`, now in `tasks/done/`.

# Human decisions or resources

- [ ] Confirm this card should stay blocked until `F6-004` reaches
      `tasks/done/`, per the agreed backend-first ordering.
- [ ] Confirm the exact page set for the minimal v1: teams list/detail,
      seasons list/detail, players list/detail, and which stat grain(s) to
      show per player — bounded by whatever `F6-004` ultimately exposes.
- [ ] Decide where frontend code lives: a subdirectory in this repository
      (e.g. `web/`) or a separate repository. ADR 0006 requires separate
      *responsibilities*, not necessarily separate repositories.
- [ ] Decide the CORS origin(s) the API must allow once a frontend exists,
      and who owns adding `CORSMiddleware` to `src/nba_data/api/app.py` —
      this card's follow-up, or a small independent API task.
- [ ] Decide whether a new `frontend`/`web` area and skill should be added to
      `.agents/index.md` before implementation starts.
- [ ] Confirm no auth or rate-limiting is required for this first pass
      (local/dev use only).

# Acceptance criteria

Not final — this card is not ready to start. Draft direction:

- A durable document (an ADR update or a new `docs/architecture/` entry)
  states the frontend's v1 page set, its data source (the `/api/v1` surface
  only), the confirmed tech stack, the repository location, and the CORS
  approach.
- A follow-up implementation card can name exact routes, components,
  fixtures, and validation commands without inventing missing decisions.

# Scope

Research and decision-making only: which pages ship first, what data they
need, where the frontend code lives, and what backend changes (CORS) that
implies.

# Out of scope

Implementing any frontend code, scaffolding Next.js, changing the API beyond
noting the future CORS need, and rankings, comparisons, OVR, or other
generated analytics — explicitly a later phase per ADR 0008.

# Impact

Potentially `src/nba_data/api/app.py` (CORS, later), a new frontend directory
or repository, `.agents/index.md`, and `docs/decisions/`.

# Implementation notes

Do not choose a page shape from the wide `stats` tables directly — wait for
`F6-004`'s settled public contract. Keep the API/frontend boundary from ADR
0006: the frontend never queries the database directly, only the API.

# Durable knowledge updates

- `docs/decisions/` — record the settled frontend v1 scope and repository
  location once decided.

# Review evidence

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
