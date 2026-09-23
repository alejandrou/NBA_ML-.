# ADR 0019 - Scope The Frontend V1

## Status

Accepted. Scopes the future phase that ADR 0008 deferred; ADR 0008's stack
choice stands.

## Context

ADR 0008 chose Next.js, TypeScript, Tailwind, and shadcn/ui for a "future web UI
for players, rankings, and comparisons" and deferred everything else. ADR 0006
requires the frontend to consume API data only.

By September 2026 the read API serves `teams` and `seasons`, and
`API_CONTRACT.md` fixes the player and statistics routes that `F6-012`,
`F6-013`, and `F6-014` will serve. The owner plans to change the database and is
unsure what the frontend should be, so the first frontend has to be small,
useful, and insulated from the database.

Four facts shape the decision:

- A season resource carries `season_year`, `league`, and a `label` that repeats
  the year. There is nothing to put on a season page.
- A team resource carries a code, an abbreviation, and a name. It is thin, but
  it is served today, and every player stint links to one.
- The player and statistics contract is the core of the dataset: 32 official
  stat tables reached one player-season at a time.
- The API binds loopback and registers no middleware, so a browser on another
  origin cannot call it.

## Decision

**Pages.** v1 is five read-only routes, and nothing else:

| Route | Shows | Served by |
|---|---|---|
| `/teams` | every team code, paginated | `GET /teams` |
| `/teams/[code]` | one team code, its abbreviation and name | `GET /teams/{code}` |
| `/players` | every player, alphabetical, paginated | `GET /players` |
| `/players/[pid]` | a player and their season index with teams | `GET /players/{pid}`, `/seasons` |
| `/players/[pid]/seasons/[year]` | one season's official statistics, one family at a time | the aggregate and stint routes |

The player season page is the page the product is built around. The teams pages
ship first only because they are the data served today, which lets the scaffold
land without waiting for any API card.

**Seasons pages are not in v1**, and neither are search, leaderboards,
comparisons, rankings, charts, career totals, biography, or anything from
`features`.

**Location.** The frontend lives in `web/` at the repository root. The owner
maintains one repository, and the API contract and its only consumer change
together; ADR 0006 separates responsibilities, not repositories.

**Ownership.** `web/` belongs to the `app` track, including its npm dependencies
and `web/package-lock.json`: they cannot break the `data` track. Workflow
integration — `AGENTS.md`, `.agents/`, and CI — is `shared` work (`WF-008`).

**Data source.** The frontend reads the public `/api/v1` contract and nothing
else: no database connection, no ORM model, no table name. A database change
that keeps the contract intact never reaches `web/`.

**Fetching and CORS.** Pages are React Server Components that call the API from
the Next.js server. The browser talks only to Next.js and never calls the API,
so the API needs no CORS policy and `create_app()` stays unchanged. The API base
URL is a server-only setting. Client-side fetching, if it is ever needed, goes
through a Next.js route handler first; exposing the API to browsers is its own
API card.

**The frontend computes nothing.** It formats values it received and derives
nothing from them: no sums of stints, no averages, no career totals, no ranks.
This extends the API's rule to the whole stack.

**Access.** No authentication and no rate limiting. v1 is local only: the API
stays on `127.0.0.1:8000`, the Next.js server binds `127.0.0.1:3001`, and there is
no deployment target.

**Stack.** Next.js App Router, TypeScript in strict mode, Tailwind CSS, shadcn/ui
components copied into the repository, Node 22 LTS, and npm with a committed
lockfile. Types for API responses are generated from a committed snapshot of the
API's OpenAPI document, so contract drift fails a check instead of a page.

The details — per-route API calls, status handling, display rules, layout,
configuration, tests, and validation commands — are in
`docs/architecture/WEB_ARCHITECTURE.md`.

## Consequences

- `F7-002` scaffolds `web/` and serves the teams pages; `F7-003` the players
  pages after `F6-012`; `F7-004` the season statistics page after `F6-013`.
  Postseason appears when `F6-014` lands.
- Finding a player means paging an alphabetical list until the API offers name
  search, which `API_CONTRACT.md` names as a deliberate non-promise. `F6-019`
  designs it.
- A career table across seasons would need one statistics request per season,
  because every statistics route is scoped to one player-season. v1 shows one
  season at a time instead of issuing those requests.
- The `web` area has durable context but no skill until `WF-008` writes one
  from the conventions `F7-002` actually establishes.

## Alternatives Considered

- **Build the player pages first against fixtures.** Rejected: it ships a
  frontend nobody can use until `F6-012` lands, and it would be the first code
  in the repository written against an unserved contract.
- **Client-side fetching with `CORSMiddleware`.** Rejected for v1: it widens the
  API's surface and adds a browser-facing origin to configure, for no page that
  needs it.
- **A separate repository.** Rejected: one owner, one contract, and the API and
  its only consumer are reviewed together.
- **Seasons pages.** Rejected: a season resource has no content beyond its
  year, and per-season rosters or leaders are non-promises of the contract.
