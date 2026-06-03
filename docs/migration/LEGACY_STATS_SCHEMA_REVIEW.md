# Legacy Stats Schema Review

## Purpose

This document reviews the useful ideas from the legacy Peewee stats schema
before Phase 4E introduces SQLAlchemy `stats` tables. It is a design review
only and does not remove or modify legacy code.

## Useful Legacy Ideas

- `models/player/player.py` captured roster-like player-team-season details.
- `models/player/player_stats.py` captured official totals-style player stats.
- `models/player/player_advanced.py` captured official advanced player stats.
- `db_manager/player_operations/player_operations.py` showed a practical flow
  where one team-season page can feed roster, totals, and advanced tables.
- The legacy column names are useful as semantic hints for official Basketball
  Reference totals and advanced columns.

## Problems Not To Copy

- Legacy stats FK to a legacy `Player` row rather than the current
  `core.player_team_seasons` or `core.player_seasons` grains.
- Legacy operations look up players by `player_name`; F4E must never use
  display names as stable keys.
- Legacy tables live under Peewee and `create_tables()` flows; new schema work
  must use SQLAlchemy 2.0 and Alembic.
- Totals and advanced are only part of the current parser coverage. F4E must
  also account for per-game, per-minute, per-possession, shooting, adjusted
  shooting, play-by-play, and roster.
- Legacy percentage fields were often strings. F4E should use numeric decimals
  for official rates, percentages, and advanced values.
- Legacy tables do not clearly separate real team stints from `TOT` aggregate
  player-season rows.

## F4E Direction

- Keep legacy code available until removal is separately approved.
- Use legacy tables only as a concept reference, not as the new persistence
  shape.
- Store official scraped stats under `stats`.
- Store future generated metrics under `features`.
- Use `core.player_team_seasons.id` for real team-stint stats.
- Use `core.player_seasons.id` for official aggregate `TOT` stats.
- Preserve official columns as wide typed relational columns instead of primary
  `JSONB`.

