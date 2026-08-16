# ADR 0007 - Handle Synthetic Team Codes and Trades

## Status

Accepted. Amended 2026-08-16 — see *Amendment*.

## Context

Basketball Reference player pages use a **multi-team marker** in the team cell
of an official full-season row after trades: the number of teams the player
appeared for, followed by `TM`. `TOT` can appear on unsupported player-page
areas such as Game Highs, but Phase 4E does not use those tables as official
season-stat sources.

## Decision

Do not model `TOT` or any multi-team marker as a team.

A **multi-team marker** is a numeric team count of at least two followed by
`TM`: `2TM`, `3TM`, `4TM`, `5TM`, and any higher count. `0TM` and `1TM` are not
markers — a one-team season is a real stint and a zero-team season is nonsense —
and neither are malformed forms such as `02TM`. The rule is the count, not a
list of values.

Use official player-page multi-team rows as full player-season source rows in
`stats.player_season_*`. Real team rows remain team stints in
`core.player_team_seasons` and `stats.player_team_season_*`.

A multi-team marker is a metadata marker in `source_team_code`, not a team.
`TOT` is distinct: it is not a multi-team marker, and it is ignored for Phase 4E
supported stats unless a later reviewed source contract explicitly adds a table
where it is the official season-stat marker.

## Consequences

Future stats tables must separate full player-season stats from
player-team-season stats. Synthetic source codes — `TOT` and every multi-team
marker — must never create `core.teams`, `core.team_aliases`,
`core.team_seasons`, or `stats.player_team_season_*` rows.

The rule has one implementation, `src/nba_data/domain/team_codes.py`, which
every layer imports. Because a check constraint cannot call Python, the same
module also generates the SQL form used by the four `core` check constraints,
and a test asserts the two forms agree.

The generated SQL recognizes a count of **any** length: it matches `<n>TM` by
deleting every digit and checking that `TM` is what remains, rather than by
enumerating digit positions, which would have to stop at some arbitrary width.
The two forms therefore agree everywhere, not merely within the range a column
can currently store.

The Alembic revision that installs the constraints carries the generated text
**frozen as a literal**, and imports nothing from this module. A revision
records one historical schema change; if it read the rule at run time, applying
it after a later rule change would produce a different schema than it produced
originally. A test asserts the frozen text still matches the module, so a rule
change surfaces as a demand for a new revision rather than as silent drift.

## Amendment — 2026-08-16 (F4E-014)

The original decision text read:

> Do not model `TOT`, `2TM`, `3TM`, or `4TM` as teams.
>
> Use official player-page `2TM`, `3TM`, and `4TM` rows as full player-season
> source rows in `stats.player_season_*`. Real team rows remain team stints in
> `core.player_team_seasons` and `stats.player_team_season_*`.
>
> `2TM`, `3TM`, and `4TM` are metadata markers in `source_team_code`, not teams.
> `TOT` is ignored for Phase 4E supported stats unless a later reviewed source
> contract explicitly adds a table where it is the official season-stat marker.

That enumeration was incomplete, and the code faithfully implemented it. The
cached archive contains a `5TM` season — Bobby Jones (`jonesbo02`), 2007-08 —
which fell outside the list, so its full-season row was never selected and the
season persisted with no regular-season aggregate stats. A `5TM` value reaching
a team writer would also have been treated as a real team.

The decision is unchanged in intent; it is restated as a rule about the team
count so no future marker falls outside it. `TOT` keeps its distinct handling.

## Alternatives Considered

- Store synthetic codes as teams: creates false team relationships.
- Generate player-season rows by summing team stints: risks incorrect
  percentages and derived advanced metrics.
