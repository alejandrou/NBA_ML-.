---
id: F8-002
title: Add the games and per-game box-score schema
track: data
areas:
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
  - docs/decisions/0020-take-per-game-data-from-basketball-reference.md
  - docs/architecture/SYSTEM_DESIGN.md
  - docs/domain/BUSINESS_RULES.md
  - docs/decisions/0007-handle-tot-and-trades.md
  - src/nba_data/db/models/core.py
  - src/nba_data/db/models/stats.py
  - src/nba_data/scraping/parsers/box_score.py
  - src/nba_data/scraping/parsers/league_schedule.py
  - alembic/versions/0008_drop_raw_schema.py
  - tests/integration/conftest.py
  - tests/integration/test_synthetic_team_code_constraints_postgres.py
validation:
  - uv run pytest tests/unit/test_game_models.py tests/unit/test_core_models.py tests/unit/test_stats_models.py tests/unit/test_impact_map_documentation.py tests/unit/test_migration_snapshots.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Applying the new revision to the persistent nba database — only from merged origin/main and with the owner's approval. Authoring it and running it in the disposable lane needs no approval.
  - None of the loading, acquisition, or 2025–26 team-page runs this card's decisions point to happen here; each needs its own card and the owner's direct instruction.
---

# Goal

Add the game grain the first team predictor needs — `core.games`,
`stats.team_game_totals`, and `stats.player_game_totals` — as one reversible
Alembic revision, with the invariants the F8-001 pilot found enforced by the
database wherever a single table or a foreign key can enforce them, and proven
on disposable PostgreSQL. No data is loaded.

# Evidence and current state

- `alembic/versions/` ends at `0008_drop_raw_schema`. Backlog cards F4E-021
  (`0009_drop_player_slug`) and F4E-033 also add revisions and may land first,
  so this revision's number and `down_revision` are whatever
  `uv run alembic heads` reports when it is written.
- No model has a game grain. `core` has seven tables, `stats` 33
  (`docs/architecture/IMPACT_MAP.md:182`, pinned by
  `tests/unit/test_impact_map_documentation.py`).
- `core.team_seasons` is keyed by code-era team identity
  (`uq_core_team_seasons_team_season`) and rejects synthetic codes such as `TOT`
  (ADR 0007, revision 0006). `core.players` is keyed by
  `basketball_reference_player_id`.
- Existing `stats` tables carry `_LineageMixin` (`source_url`, `cache_path`,
  `parser_version`, `created_at`, `updated_at`) and keep official stat columns
  nullable, so a blank is never read as zero. `core` tables carry no lineage.
- The offline suite never calls `create_all` on SQLite; schema is exercised only
  through Alembic on PostgreSQL (CI's `alembic upgrade head` → `alembic check` →
  `downgrade -1` → `upgrade head` round trip, and
  `scripts/validate_postgres_local.py`). PostgreSQL-only check conditions are
  therefore safe.
- `tests/integration/conftest.py` derives its empty-`core` guard from the mapped
  metadata, so `core.games` is covered without editing it.
- What the parsers produce (`scraping/parsers/box_score.py`,
  `league_schedule.py`):
  - game types `regular_season`, `play_in`, `playoffs`, `cup_final`
    (`unknown` when the heading does not classify);
  - participation `played`, `did_not_play`, `did_not_dress`, `not_with_team`,
    `suspended`, `other_absence`, `inactive`, plus the raw reason text;
  - per player: starter, seconds played, the 15 `COUNTING_STATS`
    (`fg fga fg3 fg3a ft fta orb drb trb ast stl blk tov pf pts`), plus-minus;
  - per team: the same counters and exact `totals_seconds`;
  - per game: venue line, attendance (blank vs 0), schedule start time as
    published ("7:30p", US Eastern), no neutral-site flag.
- Pilot findings that shape the schema (`PER_GAME_ACQUISITION_PILOT.md`):
  team totals include 0–3 team turnovers no player carries (5); attendance blank
  ≠ 0 (7); a played line can be 0:00 with blank plus-minus, and Cup-final
  plus-minus can be all zeros or absent (3, 8); inactive-only and 2025–26 players
  are missing from `core.players` (9, 10); one line score in 30 is wrong at the
  source (1).

# Human decisions or resources

- [x] **Source and fields** — settled by F8-001 and ADR 0020: Basketball
      Reference schedule and box score pages.
- [x] **First revision contents** — `core.games`, `stats.team_game_totals`,
      `stats.player_game_totals` only. The `*_source_ids` tables wait for a second
      provider: Basketball Reference ids are `core`'s own (ADR 0020), so a mapping
      table would map every id to itself. `core.game_schedule_versions` is not
      built: F8-008 keeps schedule history as page snapshots (F8-012, ADR 0022)
      and `core.games` holds the current observation. `core.roster_observations`
      waits for Stage 4; it has no consumer yet. Per-period scores are deferred too: the team
      predictor does not use them and finding 1 needs its own reconciliation.
- [x] **Public game id** — the Basketball Reference id
      (`<yyyymmdd>0<home code>`, e.g. `202310240DEN`) as text, unique. It is
      stable, already in every URL and cache path, and needs no own key.
- [x] **Final score lives in `stats`, not `core`** — the result is
      `stats.team_game_totals.pts`, the one place it is stored. `core.games`
      holds identity, schedule, and status. This follows the core/stats
      separation guardrail and leaves nothing to drift between two copies.
- [x] **Player rows reference `core.players` and `core.team_seasons`
      directly**, not `core.player_team_seasons`: 2025–26 and inactive-only
      players have no player-season rows, and the loader must not fabricate them.
      Missing players are created by the loader from box score links (stable ids,
      never names).
- [x] **Inactive players get a row** with participation `inactive` and no stats,
      so availability is kept for Stage 4.
- [x] **2025–26 `core.seasons`/`core.team_seasons`** — from the existing
      team-season pages (`/teams/<CODE>/<YEAR>.html`, not the `_games` schedule
      pages ADR 0020 excludes) extended to season 2026: one identity source, no
      team-seasons invented from box scores. That is F8-003, with its own live
      acquisition; nothing here. Season 2026-27 is in progress and its pages
      still change, so it waits for the current-season card (F8-008).
- [x] **Status `postponed` is in the first revision** (decided 2026-10-18,
      F8-008): an in-progress season's game can leave its date, and Basketball
      Reference gives the rescheduled game a new id. F8-014 marks the old row
      `postponed` instead of deleting it, so a stored forecast keeps its game.
      Adding the value now avoids a second revision of the same check. A
      scheduled row's id is built from its date and home code (`F8-014`),
      the same `<yyyymmdd>0<home code>` rule.
- [x] **Tip-off time** stored as the published local time (`time`, US Eastern,
      nullable) beside `game_date`, not converted to a timestamp: conversion
      needs time-zone data that Windows lacks without a new dependency, and the
      24-hour cutoff of Stage 2 is computed in `features`.

# Acceptance criteria

`core.games` (new model `Game` in `db/models/core.py`):

- Columns: `id` PK; `basketball_reference_game_id` text, not null, unique
  (`uq_core_games_bref_id`), check `~ '^[0-9]{8}0[A-Z]{3}$'`; `season_id` FK
  `core.seasons`, not null; `home_team_season_id` and `away_team_season_id`, not
  null; `game_date` date, not null; `start_time_et` time, null; `game_type` text,
  null, check in the four parser types (`unknown` is never stored); `status`
  text, not null, check in (`scheduled`, `final`, `postponed`); `venue` text, null;
  `neutral_site` boolean, null (null = not determined, never false by default);
  `attendance` integer, null, check `>= 0`.
- Check `home_team_season_id <> away_team_season_id`.
- Check `status <> 'final' OR game_type IS NOT NULL`.
- Composite FKs `(home_team_season_id, season_id)` and
  `(away_team_season_id, season_id)` → `core.team_seasons (id, season_id)`, so
  both teams belong to the game's season. This adds
  `uq_core_team_seasons_id_season` on `core.team_seasons` — the only change to
  an existing table, additive, and dropped by the downgrade.
- Indexes `(home_team_season_id, game_date)`, `(away_team_season_id, game_date)`,
  and `(game_date)`.

`stats.team_game_totals` (`TeamGameTotals` in `db/models/stats.py`):

- `game_id` FK `core.games`, `team_season_id` FK `core.team_seasons`, `is_home`
  boolean — all not null; uniques `(game_id, team_season_id)` and
  `(game_id, is_home)`; index `(team_season_id)`.
- `seconds_played` and `pts` not null; the other 14 counters nullable; one check
  that every counter and `seconds_played` is `>= 0`; `_LineageMixin`.
- `tov` is the team's own total, team turnovers included — documented, not a sum
  of player rows.

`stats.player_game_totals` (`PlayerGameTotals`):

- `game_id`, `player_id` FK `core.players`, `team_season_id`, `starter`,
  `participation` — all not null; `participation_reason` text, null;
  `seconds_played`, the 15 counters, and `plus_minus`, all null; `_LineageMixin`.
- Unique `(game_id, player_id)`; index `(player_id)`.
- Composite FK `(game_id, team_season_id)` → `stats.team_game_totals
  (game_id, team_season_id)`: a player line exists only for a team whose total
  for that game is loaded.
- Check `participation` in the seven parser values.
- Check: `participation = 'played'` requires `seconds_played IS NOT NULL`;
  any other participation requires `starter = false` and `seconds_played`, every
  counter, and `plus_minus` all null. A played line of zeros and a "Did Not
  Play" line are therefore always distinguishable.
- Check counters and `seconds_played` `>= 0` (`plus_minus` may be negative).

Revision and tests:

- One new revision under `alembic/versions/`, chained on the head at the time of
  writing. `alembic check` is clean; `downgrade -1` → `upgrade head` →
  `alembic check` round-trips; the downgrade leaves the schema exactly as the
  previous head (tables, indexes, and the `core.team_seasons` unique gone).
- `tests/unit/test_game_models.py` (new) asserts schemas, keys, FKs, indexes, and
  check-constraint names from the metadata, and that the allowed `game_type` and
  `participation` values equal the parser constants in
  `scraping/parsers/box_score.py` (minus `unknown`), so the two cannot drift.
- `tests/unit/test_core_models.py` and `test_stats_models.py` cover the new
  tables; `IMPACT_MAP.md` reads `core` (8) and `stats` (35 …), and its
  impact-map test passes.
- `tests/integration/test_game_schema_postgres.py` (new), in the
  `test_synthetic_team_code_constraints_postgres.py` style — every rejection
  asserts the **named** constraint PostgreSQL reports — proves on disposable
  PostgreSQL:
  - rejected: home = away; a team-season of another season; a duplicate or
    malformed game id; a final game without a type; negative attendance; a second
    row for the same side or team; a non-played line carrying any stat, seconds,
    or starter; a played line without seconds; a duplicate `(game, player)`; a
    player line whose team has no total for that game; a participation or game
    type outside the allowed set;
  - accepted: a scheduled game without type; a postponed game without type;
    attendance null and 0, read back
    distinct; a played 0:00 line with null plus-minus; a played line of zeros
    beside a `did_not_play` line with all nulls; an `inactive` line;
  - the game id reads back byte-for-byte.
- No loader, parser, or acquisition code changes.

# Scope

`src/nba_data/db/models/core.py`, `stats.py`, `__init__.py`; one new revision in
`alembic/versions/`; `tests/unit/test_game_models.py` (new),
`test_core_models.py`, `test_stats_models.py`;
`tests/integration/test_game_schema_postgres.py` (new);
`docs/architecture/SYSTEM_DESIGN.md`, `docs/domain/BUSINESS_RULES.md`,
`docs/architecture/IMPACT_MAP.md`.

# Out of scope

- Loaders, bulk acquisition, the 2025–26 team-page run, and creating players
  from box score links (F8-003 to F8-006).
- Cross-table checks the schema cannot express — a final game has exactly two
  team rows with different points; team rows are the game's own two sides;
  schedule score = box score; line-score reconciliation; Cup-final zero
  plus-minus stored as null; neutral-site derivation. The loader card gates them
  before writing; this card documents them in `BUSINESS_RULES.md`.
- Per-period scores, play-by-play, `*_source_ids`, schedule versions, roster
  observations, `features`, and `ml` tables.
- Any API route.

# Impact

- **Schema:** three new tables and one new unique on `core.team_seasons`; the
  head moves by one revision.
- **API readiness:** once the revision is applied to `nba`, the `app` worktree
  answers 503 until its next task starts from the new `origin/main` (ADR 0018) —
  the readiness contract, not a break.

# Cross-track impact

- Additive: new `core.games`, `stats.team_game_totals`, `stats.player_game_totals`
  the `app` track can serve when it chooses (plan Stage 5). The handoff card is
  `F6-020` (already in `tasks/planning/`); before review, add its line under
  `## Open` in `tasks/CROSS_TRACK.md`.

# Implementation notes

- Check `uv run alembic heads` first; if F4E-021 or F4E-033 has landed, chain on
  it and name the file with the next number.
- Write the check conditions as literals in the revision; the models declare the
  same text. If a condition is ever generated from a module, freeze it as
  revision 0006 does and pin it in `test_migration_snapshots.py`.
- Name every constraint explicitly (`ck_`, `uq_`, `fk_`, `ix_` with schema and
  table), matching the existing convention, so the integration probes can assert
  by name and `alembic check` stays clean.
- Follow-ups: F8-003 (season 2025–26 in the archive), F8-004 (gated Stage 2
  acquisition), F8-005 (the loader, with the gates listed under Out of scope),
  F8-006 (the Stage 2 acquisition and load), F8-008 (the current season).

# Durable knowledge updates

- `docs/architecture/SYSTEM_DESIGN.md` — the game grain and its natural keys
  (`core.games.basketball_reference_game_id`; `(game_id, team_season_id)`;
  `(game_id, player_id)`).
- `docs/domain/BUSINESS_RULES.md` — game and box-score invariants: participation
  vs zeros, attendance null vs 0, neutral site null = unknown, team turnovers,
  result from team totals, and the loader-enforced cross-table rules.
- `docs/architecture/IMPACT_MAP.md` — table counts and the new tables.

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
