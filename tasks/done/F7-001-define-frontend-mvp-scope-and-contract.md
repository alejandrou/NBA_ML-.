---
id: F7-001
title: Define the frontend MVP scope and contract
track: app
areas:
  - web
  - documentation
priority: 110
depends_on:
  - F6-004
read:
  - docs/decisions/0008-use-nextjs-for-future-frontend.md
  - docs/decisions/0006-separate-scraper-api-web.md
  - docs/decisions/0018-run-data-and-app-tracks-in-parallel.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/SYSTEM_DESIGN.md
  - tasks/done/F6-004-record-the-public-player-and-stats-api-contract.md
  - tasks/done/F6-003-define-api-database-readiness-contract.md
  - src/nba_data/api/app.py
  - src/nba_data/cli/main.py
validation:
  - uv run python scripts/validate_tasks.py
  - uv run pytest tests/unit/test_api_foundation.py
  - uv run pytest -m "not integration and not live"
critical_actions: []
---

# Goal

Define what the first frontend delivers, how it is built, and exactly which
pages and data it covers, so the implementation cards that follow have no
decision left to invent. The first pass is deliberately minimal: read-only views
over the `/api/v1` contract, not the players/rankings/comparisons product ADR
0008 describes as a later phase.

The owner is about to change the database and is unsure about the frontend. The
design therefore couples the frontend to the public API contract only, so a
database change that keeps the contract intact never reaches the web code.

The owner delegated every decision on this card to the agent on 2026-09-23
("up to you to take the best decisions on the first page. I won't be here to
answer the questions."). The answers under *Human decisions or resources* are
recorded in ADR 0019 and `docs/architecture/WEB_ARCHITECTURE.md`, and are open
to the owner's revision in review.

# Evidence and current state

- `src/nba_data/api/app.py` registers `health`, `teams`, and `seasons`
  routers and no middleware at all — no `CORSMiddleware`.
- `F6-004` is in `tasks/done/`. `docs/architecture/API_CONTRACT.md` specifies
  the player and statistics routes, bodies, ordering, and status codes; none is
  served yet. `F6-012` (player identity) is in `tasks/backlog/`; `F6-013` and
  `F6-014` (statistics) are in `tasks/planning/`.
- `nba-data serve` binds `127.0.0.1:8000` by default (`src/nba_data/cli/main.py`,
  `_SERVE_HOST_OPTION` / `_SERVE_PORT_OPTION`).
- ADR 0008 commits to Next.js, TypeScript, Tailwind, and shadcn/ui; ADR 0006
  requires the frontend to consume API data only.
- No frontend directory, `package.json`, or `web` skill exists.
  `.agents/index.md` routes the `web` area to ADRs 0006 and 0008 with "a skill
  is pending F7-001".
- Node `v22.18.0` and npm `10.9.3` are installed on the owner's machine; pnpm
  is not.

# Human decisions or resources

- [x] Blocked until `F6-004` is done? — No longer blocked: `F6-004` is in
      `tasks/done/`. Implementation cards depend on the serving cards they need
      (`F6-012`, `F6-013`), not on this one alone.
- [x] Exact v1 page set — teams index and detail, players index, player
      profile, and player season statistics. Seasons pages are **not** in v1:
      a season resource carries only `season_year`, `league`, and a `label`
      that repeats the year, so a page would have nothing to show. The page
      the frontend is built around is the player profile and its season
      statistics; teams ship first only because they are served today.
- [x] Code location — `web/` at the repository root, one repository.
- [x] CORS — none. The browser never calls the API: pages fetch on the Next.js
      server, from an origin-less server-to-server request, so no CORS header
      is needed and `create_app()` stays unchanged. A future client-side fetch
      goes through a Next.js route handler, or opens its own API card.
- [x] `web` skill — not before implementation. The durable context is
      `docs/architecture/WEB_ARCHITECTURE.md`; a skill is written from the
      conventions `F7-002` actually establishes, by the `shared` card `WF-008`,
      because `.agents/` and `AGENTS.md` are `shared` files.
- [x] Auth and rate limiting — none in v1. Local use only: the API stays on
      loopback and the Next.js server binds `127.0.0.1`.

# Acceptance criteria

- `docs/decisions/0019-scope-the-frontend-v1.md` records the v1 page set, the
  `/api/v1`-only data source, the stack, `web/` as the location, and the
  no-CORS server-side fetching decision. ADR 0008 points at it.
- `docs/architecture/WEB_ARCHITECTURE.md` states, for every v1 route, the exact
  API calls it makes, how each API status is rendered, the display rules the
  contract imposes, the project layout, configuration, testing strategy, and the
  exact validation commands.
- A static mockup of the first page exists in the repository at
  `docs/design/frontend-v1-player-season.html`, built only from fields the
  contract publishes.
- Follow-up cards exist: `F7-002` (scaffold and teams pages) and `F7-003`
  (players index and profile) in `tasks/backlog/`; `F7-004` (season
  statistics page), `WF-008` (bring `web/` into the workflow), and `F6-019`
  (design player name search) in `tasks/planning/`. The backlog cards name
  exact routes, components, fixtures, and validation commands; the planning
  cards list exactly what they still need.
- `docs/architecture/SYSTEM_DESIGN.md` and
  `docs/architecture/API_ARCHITECTURE.md` point at the frontend decision
  instead of describing it as undecided.
- `uv run python scripts/validate_tasks.py` passes.

# Scope

Documentation and cards only: `docs/decisions/`, `docs/architecture/`,
`docs/design/`, `tasks/`, and one `.gitignore` exception so the mockup under
`docs/design/` is not swallowed by the repository-wide `*.html` rule.

# Out of scope

Any frontend code or Next.js scaffold; any API change (CORS is decided *not*
needed); `.agents/` and `AGENTS.md`, which are `shared` and belong to
`WF-008`; rankings, comparisons, OVR, and other generated analytics.

# Impact

New ADR 0019, new `docs/architecture/WEB_ARCHITECTURE.md`, a new
`docs/design/` mockup, one-line pointers in ADR 0008, `SYSTEM_DESIGN.md`, and
`API_ARCHITECTURE.md`, a `!docs/design/*.html` line in `.gitignore`, and five
new cards.

# Cross-track impact

- None.

# Implementation notes

Do not choose a page shape from the wide `stats` tables directly; every page
reads the settled `F6-004` contract. Keep ADR 0006's boundary: the frontend
never queries the database, only the API.

# Durable knowledge updates

- `docs/decisions/0019-scope-the-frontend-v1.md` (new).
- `docs/architecture/WEB_ARCHITECTURE.md` (new).

# Review evidence

## Automated validation

- Command: `uv run python scripts/validate_tasks.py`
- Result: `Task validation passed.` (also `--all-worktrees`; the data track has since claimed F8-001; app
  holds F7-001).
- Command: `uv run pytest tests/unit/test_api_foundation.py`
- Result: 9 passed.
- Command: `uv run pytest -m "not integration and not live"`
- Result: 999 passed, 28 deselected.
- Command: `git diff --check`
- Result: clean (line-ending notices only).

## Manual happy path

1. Read `docs/decisions/0019-scope-the-frontend-v1.md`, then
   `docs/architecture/WEB_ARCHITECTURE.md`. Check that the five routes, the
   API calls per route, the no-CORS server-side fetching rule, `web/`, and the
   port `3001` are what you want.
2. Open `docs/design/frontend-v1-player-season.html` in a browser (it needs
   no server). Narrow the window to phone width, and switch your OS to dark
   mode, to see both.
3. Open the canvas https://claude.ai/artifact/Vfuba7HYuwsX4FRCMyKFnk (private
   to you): player season desktop and phone, player profile, and teams index.
   In Play, the nav, breadcrumbs, team links, and season links move between
   screens.
4. Read `tasks/backlog/F7-002-*.md` and `tasks/backlog/F7-003-*.md`: an
   implementer should need no further decision.

Expected result: every decision is recorded once, each page shows only fields
the contract publishes, and James Harden's 2020-21 values in the mockup match
the `2TM` aggregate and the BRK and HOU stints in your `nba` database.

## Manual sad path

1. Try to find, in the ADR or the architecture document, a place where the
   frontend reads the database, computes a statistic, or needs a CORS header.
2. Run `git status --short docs/design` and confirm the mockup is untracked
   (visible), not ignored.
3. Try `Start the next app task.` mentally: F7-002 depends on F7-001, so it
   stays unstartable until you move F7-001 to `done/`.

Expected result: none exists; the mockup is visible to Git; no frontend card
can start before you approve this one.

## Known limitations

- The decisions were made under your delegation, without your review; every
  one is revisable here before F7-001 moves to `done/`.
- `.agents/index.md` still says the `web` skill is "pending F7-001". Changing
  it is `shared` work, left to `WF-008`.
- The mockup shows `Age`, `Pos`, and `Awards` columns; whether the stat routes
  publish them is `F6-013`'s decision, recorded as open on `F7-004`.
- The mockup was built from a read-only query of the local `nba` database via
  `docker exec … psql` (no credentials read). The database change you plan may
  change these rows; the design does not depend on them.
