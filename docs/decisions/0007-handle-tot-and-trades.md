# ADR 0007 - Handle Synthetic Team Codes and Trades

## Status

Accepted

## Context

Basketball Reference player pages use multi-team source markers such as `2TM`,
`3TM`, and `4TM` for official full-season rows after trades. `TOT` can appear
on unsupported player-page areas such as Game Highs, but Phase 4E does not use
those tables as official season-stat sources.

## Decision

Do not model `TOT`, `2TM`, `3TM`, or `4TM` as teams.

Use official player-page `2TM`, `3TM`, and `4TM` rows as full player-season
source rows in `stats.player_season_*`. Real team rows remain team stints in
`core.player_team_seasons` and `stats.player_team_season_*`.

`2TM`, `3TM`, and `4TM` are metadata markers in `source_team_code`, not teams.
`TOT` is ignored for Phase 4E supported stats unless a later reviewed source
contract explicitly adds a table where it is the official season-stat marker.

## Consequences

Future stats tables must separate full player-season stats from
player-team-season stats. Synthetic source codes must never create
`core.teams`, `core.team_seasons`, or `stats.player_team_season_*` rows.

## Alternatives Considered

- Store synthetic codes as teams: creates false team relationships.
- Generate player-season rows by summing team stints: risks incorrect
  percentages and derived advanced metrics.
