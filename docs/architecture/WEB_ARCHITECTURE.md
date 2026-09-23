# Web architecture

The v1 web frontend: what it serves, what it reads, and the rules it follows.
ADR 0019 records the decision; this document is the specification that the
implementation cards (`F7-002`, `F7-003`, `F7-004`) build against.

## Scope: v1

Five read-only routes over the public `/api/v1` contract. No search, seasons
pages, leaderboards, comparisons, rankings, charts, career totals, biography,
generated metrics, authentication, or deployment. Everything the API does not
publish, the frontend does not show.

## Boundary

- **API only.** `web/` never opens a database connection, never names a table,
  and never imports Python. It depends on `API_CONTRACT.md`, not on the schema,
  so a database change that keeps the contract intact never reaches it.
- **Server-side fetching only.** Pages are React Server Components that call the
  API from the Next.js server. The API client imports `server-only`, so no client
  component can bundle it. The browser never calls the API, which is why the API
  serves no CORS headers — do not add `CORSMiddleware` to support a page; route
  the request through a Next.js route handler instead, or open an API card.
- **The frontend computes nothing.** It formats values it received. It never
  sums stints, averages rates, totals a career, ranks players, or fills a
  missing value.
- **No scraping, no writes.** Every API call is a `GET`.

## Stack

| Concern | Choice |
|---|---|
| Framework | Next.js, App Router, React Server Components |
| Language | TypeScript, `strict: true` |
| Styling | Tailwind CSS with CSS-variable theme tokens, light and dark |
| Components | shadcn/ui, copied into `web/src/components/ui/` — a source copy, not a runtime package |
| Runtime | Node 22 LTS (`"engines": {"node": ">=22"}`) |
| Package manager | npm, with `web/package-lock.json` committed; `npm ci` in validation |
| API types | `openapi-typescript`, generated from a committed OpenAPI snapshot |
| Lint | ESLint flat config, invoked as `eslint` (not `next lint`) |
| Tests | Vitest, React Testing Library, jsdom |

Versions are the current stable releases at scaffold time, pinned exactly in
`web/package.json` (no `^` or `~`) and locked in `web/package-lock.json`.

## Layout

```text
web/
  package.json              # scripts: dev, build, start, lint, typecheck, test, api:types
  package-lock.json
  tsconfig.json
  next.config.ts
  eslint.config.mjs
  vitest.config.ts
  components.json           # shadcn/ui configuration
  .env.example              # NBA_API_BASE_URL
  .gitignore                # node_modules, .next, .env*.local, coverage
  README.md                 # how to run against a local API
  src/
    app/
      layout.tsx            # shell: header navigation, footer API status
      page.tsx              # "/" redirects to /teams (F7-002), then /players (F7-003)
      not-found.tsx
      error.tsx             # API unreachable or failing
      teams/page.tsx
      teams/[code]/page.tsx
      players/page.tsx
      players/[pid]/page.tsx
      players/[pid]/seasons/[year]/page.tsx
    components/
      ui/                   # shadcn/ui copies
      api-status.tsx        # readiness badge
      pagination.tsx        # previous / next / "page N of M" from the envelope
      team-link.tsx         # code and name together, never name alone
      stat-table.tsx        # F7-004
    lib/
      api/
        client.ts           # apiGet, ApiError, server-only
        openapi.json        # snapshot exported from create_app()
        schema.d.ts         # generated from openapi.json; never hand-edited
        teams.ts            # listTeams, getTeam
        players.ts          # listPlayers, getPlayer, listPlayerSeasons, ... (F7-003, F7-004)
        health.ts           # getReadiness
      format.ts             # seasonLabel, formatStat
      stat-columns.ts       # display labels keyed by stored column name (F7-004)
    test/
      fixtures/             # JSON bodies copied from API_CONTRACT.md examples
```

## Configuration

| Setting | Default | Notes |
|---|---|---|
| `NBA_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | Server-only. Never prefixed `NEXT_PUBLIC_`. |

Running locally takes two processes:

```bash
uv run nba-data serve                 # API on 127.0.0.1:8000
npm --prefix web run dev              # next dev --hostname 127.0.0.1 --port 3001
```

The web port is 3001, not Next.js's default 3000, because another local service
already holds 3000 on the owner's machine.

**Every page is dynamic and every fetch is `cache: "no-store"`.** The database is
being rebuilt and reshaped, and a cached page would present stale data as
current. `next build` therefore never contacts the API, which keeps validation
offline. Caching is revisited when the data stops moving.

## Routes

Each page calls exactly these API routes and nothing else. `page` is a web query
parameter that defaults to 1; a value that is not a positive integer returns the
web 404.

| Web route | API calls | Web 404 when | Card |
|---|---|---|---|
| `/` | none — redirects | never | F7-002 |
| `/teams?page=N` | `GET /teams?page=N&page_size=100` | `page` invalid | F7-002 |
| `/teams/[code]` | `GET /teams/{code}` | API 404 | F7-002 |
| `/players?page=N` | `GET /players?page=N&page_size=100` | `page` invalid | F7-003 |
| `/players/[pid]` | `GET /players/{pid}`, `GET /players/{pid}/seasons?page_size=100` | API 404 on the player | F7-003 |
| `/players/[pid]/seasons/[year]?type=T&family=F` | `GET /players/{pid}`, `GET /players/{pid}/seasons/{year}`, `GET /players/{pid}/seasons/{year}/{T}/aggregate/{F}`, `GET /players/{pid}/seasons/{year}/{T}/stints/{F}?page_size=100` | API 404 on the player or the player season; `T` or `F` not in the contract's enumeration | F7-004 |

`T` defaults to `regular` and `F` to `per_game`. Path values are passed to the
API exactly as received: team codes are uppercase and player ids lowercase, and
the API's exact matching is the only matching — the web never re-cases a key.

A page beyond the last returns 200 with an empty list and a link back to page 1,
mirroring the API's collection rule.

A collection read with `page_size=100` that reports `total` greater than the
items it returned renders the items it has and a visible "list truncated" notice.
It never truncates silently. No v1 collection is expected to reach that bound
except `/teams` and `/players`, which paginate instead.

### Page contents

- **Teams index.** A table of code, abbreviation, and name in the API's order.
  The heading says "Teams", not "NBA teams": the collection is not
  league-scoped.
- **Team page.** Code, abbreviation, and name. Nothing else is published for a
  team in v1 — no roster, no seasons, no franchise.
- **Players index.** A table of name and player id in the API's order, with
  pagination. No search; see *Known gaps*.
- **Player profile.** The name and player id, then the season index: one row per
  season with the season label, the teams (each a `TeamLink`), and a link to that
  season's statistics page. The index follows the API's `season_year DESC` order.
- **Player season page.** The name, the season, a season-type switch (regular
  only until `F6-014`), and a family switch over the eight families. Below them,
  one table: the official **season aggregate** row first, then a visually
  separated **by team** block with one row per stint. The two blocks come from
  two different API calls and are labelled as such; nothing in the table implies
  that the aggregate is the sum of the stints.

`docs/design/frontend-v1-player-season.html` is a static mockup of the player
season page, built only from fields the contract publishes. Its values are real
rows read from the local `nba` database on 2026-09-23 (James Harden, 2020-21,
per game: a `2TM` aggregate and his BRK and HOU stints), formatted by the
display rules below.

## Status handling

| API outcome | Rendered as |
|---|---|
| 404 on a page's primary resource | Next.js `notFound()` — the web 404 page |
| 404 `Statistics not found` on an aggregate route | an empty state inside the table: "No official aggregate row for this family." |
| 200 with empty `items` on a stint route | the "by team" block reads "No team stints recorded." |
| Any other non-2xx, or the API unreachable | an `ApiError` thrown to `error.tsx`: "The data API is unavailable", with a retry link |

The page distinguishes the aggregate empty state from a missing player season by
fetching `GET /players/{pid}/seasons/{year}` first, never by comparing `detail`
strings. `error.tsx` never renders an API error body.

The footer shows readiness from `GET /health/ready` on every request: "API
ready", the fixed 503 `detail` string, or "API unreachable". The three 503
strings are fixed by the contract and safe to display.

## Display rules

These follow from `API_CONTRACT.md` and are binding on every page.

- **A team is its code.** Always render the code beside the name
  (`CHO · Charlotte Hornets`). Never group, merge, or link teams by name —
  `CHH` and `CHO` share one. Never imply franchise lineage between codes.
  `current_abbreviation` may be null; `current_name` may still equal the code on
  rows loaded before the team-name rebuild. Render both as received.
- **A season is its year.** Render `season_year` Y as the span `(Y-1)-YY`
  (`2024` → `2023-24`). Never parse `label`.
- **A missing stat is an em dash.** `null` renders as `—`, never `0` and never a
  blank cell; the column stays.
- **Numbers are formatted, not changed.** Columns ending in `_pct` render with
  three decimals and no leading zero (`0.4661` → `.466`); other decimal columns
  with one decimal; integers as received. Formatting rounds for display and
  never feeds a calculation.
- **Multi-team rows branch on the boolean.** When `is_multi_team` is true,
  `source_team_code` is plain text (`2TM`), never a link. When it is false and
  non-null, it is a `TeamLink`. `TOT` is never rendered as a team; if it ever
  arrives, it is plain text.
- **Columns come from the response.** A stat table renders the stat columns the
  API returns, in the order it returns them, after the identity fields
  (`season_year`, `season_type`, `source_team_code`, `is_multi_team`,
  `basketball_reference_team_id`). `stat-columns.ts` maps stored names to display
  headers (`fg3a` → `3PA`); a column without a label renders under its stored
  name. JSON keys are never renamed in the data layer.
- **Keys, not surrogates.** The player id and team code are shown as secondary
  text; no other identifier exists to show.

## Design direction

A dense, data-first reference: the table is the page.

- Warm neutral surfaces, one hardwood-orange accent for links and the active
  switch, and full light and dark themes from the same tokens.
- Type: a condensed display face for names and headings (Barlow Condensed), a
  plain sans for body and tables (IBM Plex Sans, tabular figures), and a mono
  for keys (IBM Plex Mono). Fonts ship with the app — `next/font/local` or
  `@fontsource` packages — never `next/font/google`, which downloads at build
  time and would break the offline build.
- Tabular, right-aligned numerals (`font-variant-numeric: tabular-nums`); text
  columns left-aligned.
- Wide stat tables scroll horizontally inside their own container with a sticky
  first column and header; the page body never scrolls sideways.
- Switches are links that change the URL, so every view is shareable and works
  without client JavaScript.
- Works at phone width: navigation collapses, tables scroll.

## Testing

Tests stay offline, as everywhere in this repository: no test calls a running
API.

- **Unit tests** for `format.ts`, `stat-columns.ts`, and `client.ts` (status to
  `ApiError` mapping, `no-store`, base URL joining) with `fetch` mocked.
- **Component tests** for `TeamLink`, `Pagination`, `ApiStatus`, and `StatTable`
  rendered from JSON fixtures copied from the contract's examples, including the
  null-stat, multi-team, and empty-stint cases.
- **Pages** are thin compositions of the above and are verified by `next build`
  and the manual review steps on each card.
- **Contract drift.** `web/src/lib/api/openapi.json` is exported from
  `create_app().openapi()` by `scripts/export_openapi.py`, which needs no
  database. `tests/unit/test_web_openapi_snapshot.py` fails when the snapshot and
  the live app disagree, so an API change that forgets its consumer fails
  `pytest`. The fix is to re-export the snapshot and run
  `npm --prefix web run api:types`.

## Validation commands

Focused first, global last:

```bash
npm --prefix web ci
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
uv run python scripts/export_openapi.py --check web/src/lib/api/openapi.json
uv run pytest tests/unit/test_web_openapi_snapshot.py
uv run ruff check .
uv run pytest -m "not integration and not live"
```

## Known gaps

- **No player search.** Finding a player means paging the alphabetical index.
  The contract names search as a deliberate non-promise; `F6-019` designs it.
- **No career table.** Every statistics route addresses one player-season, so a
  career table would issue one request per season. v1 shows one season at a
  time.
- **No CI job for `web/`.** Until `WF-008`, the web validation commands run
  locally only; the OpenAPI snapshot test runs in the existing `pytest` lane.
