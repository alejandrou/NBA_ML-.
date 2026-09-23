---
id: F8-002
title: Add the games and per-game box-score schema
track: data
areas:
  - planning
  - database-schema
  - data-quality
  - testing
  - documentation
priority: 105
depends_on:
  - F8-001
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - docs/decisions/0019-take-per-game-data-from-basketball-reference.md
  - docs/architecture/SYSTEM_DESIGN.md
  - docs/domain/BUSINESS_RULES.md
  - docs/decisions/0007-handle-tot-and-trades.md
  - docs/decisions/0011-nba-only-initial-scope.md
  - src/nba_data/db/models/core.py
  - src/nba_data/db/models/stats.py
  - alembic/versions/0008_drop_raw_schema.py
validation: []
critical_actions:
  - Applying the new revision to the persistent nba database — only from merged origin/main and with the owner's approval.
---

# Goal

Create the game-grain tables of `docs/ml/PREDICTOR_PLAN.md` §3 that the first
team predictor needs — games, provider id mappings, and team and player box
scores — as one Alembic revision, tested on disposable PostgreSQL, shaped by
what the `F8-001` pilot actually acquired.

# Evidence and current state

- `alembic/versions/` ends at `0008_drop_raw_schema`; no model has a game grain.
- `core.seasons` covers 1999–2000 to 2024–25 (inspection of 2026-09-12); the
  current season has no `core.seasons` or `core.team_seasons` rows, so games of
  2025–26 have no team-season to reference yet.
- `core.team_seasons` is keyed by code-era team identities
  (`uq_core_team_seasons_team_season`); `TOT` is never a team (ADR 0007).
- Player identity is `core.players.basketball_reference_player_id`; a second
  provider's ids need a mapping table, never a name match.
- The `F8-001` pilot (`docs/validation/PER_GAME_ACQUISITION_PILOT.md`, ADR 0019)
  settles the source and shows what the pages carry:
  - Provider: Basketball Reference. Its game id, `<yyyymmdd>0<home code>`
    (`202310240DEN`), is stable. Its player and team ids are `core`'s own, so
    no source-id mapping is needed while it is the only provider.
  - Game type is read from the box score heading: regular season, play-in,
    playoffs, or the NBA Cup final, which does not count. Schedule pages mark
    only play-in games.
  - Neutral site is never flagged. The venue line ("Accor Arena, Paris,
    France") always is.
  - Attendance is blank when unpublished and 0 when there were no fans.
  - Team totals include team turnovers (0–3 per game) that no player line
    carries.
  - Player seconds are rounded per line; a played line can have 0:00.
  - Plus-minus may be missing or all zeros in Cup finals.
  - Participation: played, "Did Not Play", "Did Not Dress", "Not With Team", or
    inactive, which has no line at all.
  - A line score can disagree with the play-by-play and the page's quarter
    boxes (one of 30 games), so period scores need their own reconciliation.
  - Inactive-only players can be missing from `core.players`: they appear only in
    team salary tables, which the loader does not read.
  - 2025–26 games name two to seven players per game that `core` does not hold.

# Human decisions or resources

- [x] Resolved by `F8-001`: provider Basketball Reference; league schedule,
      box score, and play-by-play pages; fields as listed under Evidence.
      Recommendations from the pilot for the decisions below, for
      `prepare-task` to confirm:
      - first revision: `core.games`, `stats.team_game_totals`, and
        `stats.player_game_totals`, with game type, venue, attendance,
        participation, and nullable plus-minus. The `*_source_ids` tables wait
        for a second provider; schedule versions wait for upcoming-game loading
        (Stage 5); roster observations wait for Stage 4.
      - public game id: the Basketball Reference id, as text.
      - 2025–26 rows: the existing team-page path, extended to season 2026 (30
        team pages); new players from box score links.
- [ ] **First revision contents.** Plan tables for Stage 2 only (`core.games`,
      `core.game_source_ids`, `core.player_source_ids`,
      `core.team_season_source_ids`, `stats.team_game_totals`,
      `stats.player_game_totals`), or also `core.game_schedule_versions` and
      `core.roster_observations` now?
- [ ] **Public game id.** The provider's id (e.g. NBA.com `0022400001`, stored
      as text) or an own reproducible key such as date + home + away?
- [ ] **Current season rows.** How 2025–26 `core.seasons`/`core.team_seasons`
      rows get created: from Basketball Reference team pages (existing path) or
      from the new provider.

# Acceptance criteria

To be written once `F8-001` reports. Fixed by the plan already:

- Home ≠ away, both in the game's season; a final game has two team rows and a
  consistent result.
- "Did not play" is distinct from a zero stat line.
- Source ids are text and keep leading zeros; ambiguous mappings are held for
  review, never resolved by name.
- Unique keys make every load idempotent; indexes cover team+date and
  player+date.
- Migration tested only on disposable PostgreSQL.

# Scope

`src/nba_data/db/models/`, one new `alembic/versions/0009_*` revision,
`tests/`, `docs/architecture/SYSTEM_DESIGN.md`, `docs/domain/BUSINESS_RULES.md`.

# Out of scope

Loaders and bulk acquisition (a later card). Play-by-play, `features`, and `ml`
tables. Any API route — that is `app` work after a handoff.

# Impact

- **Schema:** new `core` and `stats` tables; head moves to `0009`.
- **API readiness:** the `app` worktree reports not-ready until its database is
  at the new head (ADR 0018).

# Cross-track impact

- None.

# Implementation notes

- Additive only; no existing table or public identity changes.
- Record the new tables in the `app` track's view only when an endpoint needs
  them (plan Stage 5), through a handoff card and `tasks/CROSS_TRACK.md`.

# Durable knowledge updates

- `docs/architecture/SYSTEM_DESIGN.md` — the game grain.
- `docs/domain/BUSINESS_RULES.md` — game and box-score invariants.

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
