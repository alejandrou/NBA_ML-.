# Legacy Stats Schema Review

## Purpose

This document reviews the useful ideas from the legacy Peewee stats schema
before Phase 4E introduces SQLAlchemy `stats` tables. It is a design review
only and does not remove or modify legacy code.

## Useful Legacy Ideas

- `models/player/player.py` captured roster-like player/team-season details.
- `models/player/player_stats.py` captured official totals-style player stats.
- `models/player/player_advanced.py` captured official advanced player stats.
- `db_manager/player_operations/player_operations.py` showed a practical flow
  where one team-season page can feed roster, totals, and advanced tables.
- The legacy column names are useful semantic hints for Basketball Reference
  totals and advanced fields.

## Conceptual Correspondence

- Legacy `player_stats` corresponds conceptually to the Phase 4E `totals`
  family.
- Legacy `player_advanced` corresponds conceptually to the Phase 4E `advanced`
  family.
- Legacy roster is retained as an idea, but F4E models it as
  `stats.player_team_season_roster` at the `core.player_team_seasons.id`
  grain.
- Legacy team and team-season models remain separate conceptual references for
  `core`; official player statistics do not move into `core`.

## Problems Not To Copy

- Do not link stats to players by `player_name`.
- Do not use `player_name` as a stable primary or natural key.
- Do not use a loose `year` column as identity.
- Do not FK official stats to a legacy roster row as the player identity.
- Do not store numeric official stats or percentages as `CharField`.
- Do not use Peewee or `create_tables()` for new schema work.
- Do not insert without idempotent unique constraints.
- Do not mix identity, season, team membership, and official stats in one
  entity.
- Do not treat `TOT` as a real team.
- Do not treat `2TM`, `3TM`, or `4TM` as real teams.
- Do not copy the legacy limitation of only covering roster, totals, and
  advanced; Phase 4E covers all nine currently supported source families.

## F4E Direction

- Keep legacy code available until removal is separately approved.
- Use legacy code only as a concept reference, not as the new persistence
  shape.
- Store official scraped stats under schema `stats`.
- Store future generated metrics under schema `features`.
- Use `core.player_team_seasons.id` for real team-stint stats.
- Use `core.player_seasons.id` for official player-page full-season stats.
- Store player-page `2TM`, `3TM`, and `4TM` as source metadata only, not
  teams.
- Preserve official columns as wide typed relational columns instead of primary
  `JSONB`.
- Keep all stat rows idempotent through a unique constraint at their reviewed
  FK grain.
