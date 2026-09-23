---
id: F7-002
title: Scaffold the web app and serve the teams pages
track: app
areas:
  - web
  - api
  - testing
priority: 80
depends_on:
  - F7-001
read:
  - docs/decisions/0019-scope-the-frontend-v1.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - docs/design/frontend-v1-player-season.html
  - src/nba_data/api/app.py
  - src/nba_data/api/schemas/teams.py
  - tests/unit/test_api_foundation.py
validation:
  - npm --prefix web ci
  - npm --prefix web run lint
  - npm --prefix web run typecheck
  - npm --prefix web test
  - npm --prefix web run build
  - uv run python scripts/export_openapi.py --check web/src/lib/api/openapi.json
  - uv run pytest tests/unit/test_web_openapi_snapshot.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions: []
---

# Goal

Create the `web/` Next.js application specified in
`docs/architecture/WEB_ARCHITECTURE.md` and serve its first two routes,
`/teams` and `/teams/[code]`, from the teams API that is live today. This card
establishes every convention the later pages reuse: the server-only API client,
the generated types, the shell, status handling, tests, and the contract-drift
check.

# Evidence and current state

- No `web/` directory, `package.json`, or Node tooling exists in the repository.
- `GET /api/v1/teams` and `GET /api/v1/teams/{basketball_reference_team_id}` are
  served (`src/nba_data/api/routers/teams.py`); `GET /api/v1/health/ready` is
  served.
- `create_app()` builds the FastAPI app without touching the database, so
  `create_app().openapi()` can be exported offline.
- Node `v22.18.0` and npm `10.9.3` are installed on the owner's machine.

# Human decisions or resources

- None.

# Acceptance criteria

- `web/` matches the F7-002 portion of the layout in `WEB_ARCHITECTURE.md`:
  `package.json` with exact version pins, `"engines": {"node": ">=22"}`, and the
  scripts `dev` (`next dev --hostname 127.0.0.1 --port 3001`), `build`,
  `start`, `lint` (`eslint .`), `typecheck` (`tsc --noEmit`), `test`
  (`vitest run`), and `api:types`; a committed `package-lock.json`;
  `.env.example` with `NBA_API_BASE_URL`; a `.gitignore` excluding
  `node_modules`, `.next`, `.env*.local`, and coverage; and a `README.md` with
  the two-process run instructions.
- `web/src/lib/api/client.ts` imports `server-only`, reads `NBA_API_BASE_URL`
  (default `http://127.0.0.1:8000/api/v1`), fetches with `cache: "no-store"`,
  and throws an `ApiError` carrying the HTTP status for any non-2xx or network
  failure.
- `web/src/lib/api/openapi.json` is exported by `scripts/export_openapi.py`
  from `create_app().openapi()`; `--check` exits non-zero when the committed
  snapshot differs. `web/src/lib/api/schema.d.ts` is generated from it by
  `npm --prefix web run api:types`, and `teams.ts` / `health.ts` use those
  generated types.
- `tests/unit/test_web_openapi_snapshot.py` fails when the snapshot and
  `create_app().openapi()` disagree, and its message names both regeneration
  commands.
- `/` redirects to `/teams`.
- `/teams?page=N` renders code, abbreviation, and name for each team in API
  order from `GET /teams?page=N&page_size=100`, with `Pagination` driven by the
  envelope. A non-positive or non-integer `page` renders the web 404; a page past
  the end renders an empty state linking to page 1.
- `/teams/[code]` renders one team from `GET /teams/{code}`, passing the code
  verbatim; an API 404 renders the web 404 page, so `/teams/atl` is a 404 while
  `/teams/ATL` is not.
- Every team reference renders through `TeamLink` as code and name together.
- The shell (`layout.tsx`) has header navigation with "Teams", and a footer
  `ApiStatus` showing "API ready", the fixed 503 `detail` string, or "API
  unreachable" from `GET /health/ready`.
- `error.tsx` renders "The data API is unavailable" with a retry link and never
  renders an API error body.
- Theming uses shadcn/ui CSS-variable tokens with light and dark palettes, and
  the pages follow the *Design direction* in `WEB_ARCHITECTURE.md`.
- Vitest covers `client.ts` (base URL joining, `no-store`, status-to-`ApiError`),
  `TeamLink`, `Pagination`, and `ApiStatus`, from fixtures under
  `web/src/test/fixtures/` copied from `API_CONTRACT.md`. No test calls a live
  API.
- `npm --prefix web run build` succeeds while no API is running.
- `src/nba_data/api/` is unchanged.

# Scope

`web/` (new), `scripts/export_openapi.py` (new),
`tests/unit/test_web_openapi_snapshot.py` (new), and
`docs/architecture/WEB_ARCHITECTURE.md` if the implementation settles a detail
the document leaves open.

# Out of scope

Player pages (`F7-003`), statistics pages (`F7-004`), any API or schema change,
`CORSMiddleware`, CI, `AGENTS.md`, and `.agents/` (`WF-008`), deployment.

# Impact

A new `web/` Node project, one new Python script and one new unit test. The
existing `pytest` lane gains the snapshot test, so later API cards that change
the OpenAPI document must re-export the snapshot.

# Cross-track impact

- None.

# Implementation notes

- Scaffold with `npx create-next-app@latest web --ts --tailwind --eslint --app
  --src-dir --import-alias "@/*" --use-npm`, then `npx shadcn@latest init` inside
  `web/`. Both download packages from the npm registry — routine tooling, like
  `uv sync`, not data acquisition.
- Replace the scaffold's `next lint` script with `eslint .`, and pin the
  generated dependency ranges to exact versions before locking.
- Keep pages thin: fetch through `lib/api/*.ts`, call `notFound()` on an
  `ApiError` with status 404, and let every other `ApiError` reach `error.tsx`.
- `scripts/export_openapi.py` must write deterministic JSON (sorted keys,
  two-space indent, trailing newline) so `--check` is stable on Windows and
  Linux.
- `web/` is not yet listed in `AGENTS.md`'s paths; that is `WF-008`'s job and
  does not block this card.

# Durable knowledge updates

- `docs/architecture/WEB_ARCHITECTURE.md` — record any convention this card
  settles that the document leaves open.

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
