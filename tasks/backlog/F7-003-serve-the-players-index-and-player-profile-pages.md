---
id: F7-003
title: Serve the players index and player profile pages
track: app
areas:
  - web
  - testing
priority: 75
depends_on:
  - F7-002
  - F6-012
read:
  - docs/decisions/0019-scope-the-frontend-v1.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - docs/design/frontend-v1-player-season.html
validation:
  - npm --prefix web ci
  - npm --prefix web run lint
  - npm --prefix web run typecheck
  - npm --prefix web test
  - npm --prefix web run build
  - uv run python scripts/export_openapi.py --check web/src/lib/api/openapi.json
  - uv run pytest tests/unit/test_web_openapi_snapshot.py
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions: []
---

# Goal

Serve `/players` and `/players/[pid]` from the player identity routes `F6-012`
delivers, and make the players index the site's front door.

# Evidence and current state

- `F7-002` establishes `web/`, the API client, generated types, the shell, and
  `TeamLink`.
- `F6-012` serves `GET /players`, `GET /players/{pid}`,
  `GET /players/{pid}/seasons`, and `GET /players/{pid}/seasons/{season_year}`
  with the bodies fixed in `API_CONTRACT.md`.

# Human decisions or resources

- None.

# Acceptance criteria

- The OpenAPI snapshot is re-exported and `schema.d.ts` regenerated, so the
  player types come from the served API.
- `/` redirects to `/players`, and the header navigation reads "Players",
  "Teams".
- `/players?page=N` renders each player's name (linking to the profile) and
  player id, in API order, from `GET /players?page=N&page_size=100`, with
  `Pagination`; `page` handling matches `/teams`.
- `/players/[pid]` renders the name and player id, then the season index from
  `GET /players/{pid}/seasons?page_size=100`: season label (`2023-24`), each team
  as a `TeamLink`, and a link to `/players/[pid]/seasons/[year]`. The link may
  404 until `F7-004`; that is acceptable and noted in review.
- The pid is passed verbatim; an API 404 renders the web 404, so
  `/players/JAMESLE01` is a 404.
- A seasons response whose `total` exceeds its items renders the visible
  "list truncated" notice.
- `format.ts` provides `seasonLabel`, unit-tested including the century
  boundary (`2000` → `1999-00`).
- Component tests cover the season index from contract fixtures, including a
  multi-team season (`teams` with two codes) and a player with no seasons.

# Scope

`web/src/app/players/`, `web/src/app/page.tsx`, `web/src/app/layout.tsx`,
`web/src/lib/api/`, `web/src/lib/format.ts`, `web/src/components/`, and their
tests and fixtures.

# Out of scope

The season statistics page (`F7-004`), search (`F6-019`), biography, career
totals, and any API change.

# Impact

Two new routes and the site's default landing page.

# Cross-track impact

- None.

# Implementation notes

- The profile header shows no career span or totals: the frontend computes
  nothing (ADR 0019).
- The season index's `teams` is stint membership, not statistics — render it as
  links only.

# Durable knowledge updates

- None.

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
