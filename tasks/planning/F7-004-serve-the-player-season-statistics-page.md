---
id: F7-004
title: Serve the player season statistics page
track: app
areas:
  - planning
  - web
  - testing
priority: 70
depends_on:
  - F7-003
  - F6-013
read:
  - docs/decisions/0019-scope-the-frontend-v1.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - docs/design/frontend-v1-player-season.html
  - src/nba_data/db/models/stats.py
validation: []
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
  `is_multi_team` rule. `F6-013` serves the regular-season routes and is still in
  `tasks/planning/`; `F6-014` serves postseason.
- The stat families also store `rk`, `age`, `position`, `awards`, and
  `player_name_display` (`src/nba_data/db/models/stats.py`). The contract
  excludes `player_name_display`; whether `F6-013` publishes the others is not
  settled until its bodies are.

# Human decisions or resources

- [ ] Which non-statistical columns (`rk`, `age`, `position`, `awards`) the page
      shows — bounded by what `F6-013`'s response bodies actually publish.
- [ ] Whether the season-type switch ships here with postseason enabled (only if
      `F6-014` is done by then) or regular-only with postseason as a follow-up.
- [ ] The display labels in `stat-columns.ts` for all eight families, and the
      family switch's labels and order.

# Acceptance criteria

Draft direction, settled once `F6-013` is:

- The page makes exactly the four API calls `WEB_ARCHITECTURE.md` lists, and
  renders the web 404 for an unknown player, an unknown player season, or a `T`
  or `F` outside the contract's enumeration.
- `StatTable` renders the aggregate row, then the stints, with the display rules
  in `WEB_ARCHITECTURE.md` — em dash for `null`, `_pct` formatting,
  multi-team markers as plain text, stint teams as `TeamLink`.
- An aggregate 404 and an empty stint collection render their empty states; no
  `detail` string is compared.
- Component tests cover every family's fixture, a multi-team season, a `null`
  column, and both empty states.

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
