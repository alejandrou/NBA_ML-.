# Current Phase

Phase ID: `phase-3-parser-normalization`
Status: `done`

## Phase 3 - Parser Normalization

## Goal

Expand pure parsing and normalization for cached NBA source HTML while keeping
network, parsing, normalization, validation, and loading responsibilities
separate.

## Completed Work

- `F3-001` expanded pure team-season table parsing.
- `F3-002` added separated normalization for parsed team-season rows.
- `F3-003` added offline data-quality checks for normalized rows.

## Supported Parser Tables

- `roster` from table id `roster`
- `totals` from table id `totals_stats`
- `per_game` from table id `per_game_stats`
- `per_minute` from table id `per_minute_stats`
- `per_poss` from table id `per_poss`
- `advanced` from table id `advanced`
- `shooting` from table id `shooting`
- `adj_shooting` from table id `adj_shooting`
- `pbp` from table id `pbp_stats`

## Closure Notes

- Parsers remain pure HTML-string functions with no network or DB access.
- Normalized rows carry league, season, team, source table, stat scope,
  player identifier, identifier status, and conservative scraped values.
- `TOT` is classified as a player-season aggregate, not as a real team.
- `player_name` remains descriptive only and is not used as a stable key.
- Validation passed offline; no live scraping, Basketball Reference contact,
  DB writes, DB migrations, legacy/Peewee deletion, API/frontend/OVR work,
  branch, PR, commit, or push occurred.

## Next Phase Recommendation

Recommended next phase: `phase-4-sqlalchemy-migration`.

Do not activate Phase 4 without explicit owner approval.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-3-parser-normalization.md`
- `tasks/feature-list.json`
- `docs/validation/TEAM_SEASON_PIPELINE.md`
