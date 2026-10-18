---
id: F7-004
title: Serve the player season statistics page
track: app
areas:
  - web
  - testing
priority: 70
depends_on:
  - F7-003
  - F6-013
  - F6-014
read:
  - docs/decisions/0019-scope-the-frontend-v1.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - docs/design/frontend-v1-player-season.html
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/db/models/stats.py
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

Serve `/players/[pid]/seasons/[year]?type=T&family=F`: one player-season's
official statistics for one family, with the season aggregate row above a
separated "by team" block of stints, as specified in `WEB_ARCHITECTURE.md` and
drawn in `docs/design/frontend-v1-player-season.html`.

# Evidence and current state

- `API_CONTRACT.md` fixes the routes, the eight families, the aggregate and stint
  identity fields, `null` for a missing stat, rates as JSON numbers, and the
  `is_multi_team` rule. `F6-013` (regular) and `F6-014` (postseason) are in the
  backlog with their bodies settled: every stored family column except
  `player_name_display`, so `rk`, `age`, `position`, and `awards` are published.
- `F6-014` has the higher priority in the `app` track (85 vs 70), so both season
  types are served before this page starts.
- `scripts/export_openapi.py` and `tests/unit/test_web_openapi_snapshot.py` are
  created by `F7-002`; the validation list assumes it has landed.

# Human decisions or resources

- [x] **Non-statistical columns**: show `age`, `position` (where the family has
      it), and `awards` (as received, plain text). Hide `rk`: it is the row's
      rank in a Basketball Reference listing and means nothing on one player's
      page.
- [x] **Season-type switch ships with postseason enabled**; the card depends on
      `F6-014`. A postseason aggregate 404 renders the existing empty state.
- [x] **Labels are Basketball Reference's own column headers** (`fg3_pct` →
      `3P%`, `mp_per_game` → `MP`, `ws_per_48` → `WS/48`), one entry per stored
      column in `stat-columns.ts`, with the stored name as the cell's `title`.
      A component test fails when a family's API body has a field with no
      label, so a new column cannot render unlabeled.
- [x] **Family switch**, in Basketball Reference's player-page order: Per Game
      (`per_game`, the default), Totals, Per 36 Min (`per_minute`), Per 100 Poss
      (`per_poss`), Advanced, Adjusted Shooting (`adj_shooting`), Shooting,
      Play-by-Play (`pbp`).

# Acceptance criteria

- The page makes exactly the four API calls `WEB_ARCHITECTURE.md` lists, and
  renders the web 404 for an unknown player, an unknown player season, or a `T`
  or `F` outside the contract's enumeration.
- `StatTable` renders the aggregate row, then the stints, with the display rules
  in `WEB_ARCHITECTURE.md` — em dash for `null`, `_pct` formatting,
  multi-team markers as plain text, stint teams as `TeamLink`.
- An aggregate 404 and an empty stint collection render their empty states; no
  `detail` string is compared.
- Component tests cover every family's fixture, a multi-team season, a `null`
  column, both empty states, the postseason switch, `rk` absent, and the
  label-coverage check.

# Scope

`web/src/app/players/[pid]/seasons/`, `web/src/components/stat-table.tsx`,
`web/src/lib/stat-columns.ts`, `web/src/lib/api/players.ts`, and their tests.

# Out of scope

Career tables, charts, leaderboards, comparisons, and any API change.

# Impact

The page the frontend is built around.

# Cross-track impact

- None.

# Implementation notes

Never compute a value from the response — no totals, no per-game conversion, no
aggregate reconstructed from stints.

# Durable knowledge updates

- `docs/architecture/WEB_ARCHITECTURE.md` — the settled column set.

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
