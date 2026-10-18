---
id: F7-005
title: Serve the games and prediction pages
track: app
areas:
  - web
  - testing
priority: 65
depends_on:
  - F7-002
  - F6-020
  - F6-021
read:
  - docs/decisions/0019-scope-the-frontend-v1.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - docs/ml/PREDICTOR_PLAN.md
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

Let the owner pick a date, see its games, and open one to read its box score
or, for an upcoming game, its forecast — the plan's "OKC vs Chicago tonight" in
the browser.

# Evidence and current state

- ADR 0019 scoped the frontend v1 to teams and players; its 2026-10-18
  amendment adds games and forecasts.
- `F6-020` serves `/api/v1/games` (filters `date_from`, `date_to`, `team`,
  `status`, …), `/games/{game_id}` with both teams' totals, and
  `/games/{game_id}/players`; status is `scheduled`, `final`, or `postponed`.
  `F6-021` serves `/games/{game_id}/prediction`: 200 `available` or
  `unavailable` with a reason, or 404 `Prediction not found`.
- `WEB_ARCHITECTURE.md` fixes server-side fetching, generated types from the
  OpenAPI snapshot, the em dash for `null`, and "never compute a value from the
  response".

# Human decisions or resources

- [x] **Scope: games join the frontend v1** (decided 2026-10-18, recorded as an
      amendment in ADR 0019). It is the page the predictor exists for.
- [x] **Pages**: `/games?date=YYYY-MM-DD` (default: today, US Eastern), with
      previous/next-day links, and `/games/[gameId]` with the score, both team
      totals, and the player lines; the forecast block appears on a game whose
      `F6-021` response is 200, and "Forecast unavailable: <reason>" when its
      status is `unavailable`. A 404 `Prediction not found` shows no block.
- [x] **Teams on game rows** are `TeamLink`s by code with the season's
      abbreviation, per the display rules.
- [x] **No derived values**: the page shows the stored probabilities and
      favorite; no odds, no rounding beyond display, no winner computed beyond
      showing both scores.
- [x] **Display**: probabilities as percentages with one decimal
      (`0.512345` → `51.2%`), the favorite named, the model version and
      `data_as_of` in small print, and "Not adjusted for player availability"
      while `availability_included` is false (plan §3). A `postponed` game shows
      "Postponed" and no score. Seconds show as `mm:ss` in the player table —
      formatting, not a derived value. Reasons show as fixed text:
      `team_season_missing` → "A team's season is not loaded",
      `insufficient_history` → "Too few games played yet",
      `game_not_scheduled` → "The game is no longer scheduled".
- [x] **API calls**: `/games?date=` calls `/api/v1/games?date_from=D&date_to=D`
      once (page size 100, enough for one day); `/games/[gameId]` calls the
      game, its players, and its prediction — three calls in parallel.

# Acceptance criteria

- `WEB_ARCHITECTURE.md`'s route table gains `/games` and `/games/[gameId]` with
  the API calls above, first; each page makes only those calls.
- Types come from the regenerated OpenAPI snapshot (F6-020 and F6-021 merged);
  no hand-written response type.
- `/games` with no `date` uses today in `America/New_York` through
  `Intl.DateTimeFormat` (no date library); an invalid `date` renders the
  not-found page; previous/next links are plain `<a>` to the adjacent dates.
- Component tests: a day with no games; a final game (both scores, no
  forecast block on its 404); a scheduled game with an available forecast
  (percentages, favorite, the availability note) and with each unavailable
  reason; a postponed game; an inactive player line (every stat as the em
  dash); `null` attendance vs `0`; `null` neutral site; an unknown game id
  → the web 404 (`notFound()`); any other non-2xx → `error.tsx`, per
  `WEB_ARCHITECTURE.md`'s status table, which gains the prediction's 404 row
  ("no forecast block").
- Every `TeamLink` uses the season's abbreviation from the game body.

# Scope

`web/src/app/games/` (two pages and their components), `web/src/lib/api/`
(regenerated snapshot and types, client calls), web component tests,
`docs/architecture/WEB_ARCHITECTURE.md`, and ADR 0019 only if its amendment
needs a correction.

# Out of scope

Any API change (F6-020, F6-021). Team or player game logs. Odds, betting, or
any value computed from the response. A date picker beyond previous/next links.
Live score updates.

# Impact

- New web pages; `WEB_ARCHITECTURE.md` and possibly ADR 0019.

# Cross-track impact

- None.

# Implementation notes

- "Today, US Eastern" is a display default only; the API filters by date.

# Durable knowledge updates

- `docs/architecture/WEB_ARCHITECTURE.md`; ADR 0019 if amended.

# Review evidence

Filled in before the card moves to `tasks/review/`.

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
