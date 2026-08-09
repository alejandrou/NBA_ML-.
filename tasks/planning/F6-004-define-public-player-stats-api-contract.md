---
id: F6-004
title: Define the public player and official-stats API contract
areas:
  - planning
  - api
  - database-read
  - data-quality
priority: 100
depends_on:
  - F5-005
  - F5-006
read:
  - docs/architecture/API_CONTRACT.md
  - docs/domain/BUSINESS_RULES.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/db/models/core.py
  - src/nba_data/db/repositories/stats.py
  - src/nba_data/validation/official_stats.py
validation: []
critical_actions: []
---

# Goal

Define which player and official-statistic entities the public API exposes and
at what grain, so implementation does not accidentally collapse player-season,
team-stint, regular-season, and postseason data into one contract.

# Evidence and current state

- `core.players`, `core.player_seasons`, and `core.player_team_seasons` already
  model a global player and its season/stint relationships.
- The `stats` schema contains separate regular-season and postseason wide table
  families, with separate aggregate and team-stint grains. The official stats
  documents explicitly prohibit mixing those grains or synthesizing aggregate
  rows from stints.
- The API currently has only health, teams, and seasons routes. There are no
  player query repositories, player schemas, statistics query repositories, or
  public player/statistics routes.
- `BUSINESS_RULES.md` establishes Basketball Reference player IDs as the stable
  identifier when available, but `API_CONTRACT.md` does not yet define the public
  key, route shapes, filters, or missing-stat behavior.
- The team identity decision in F5-006 can affect how public player stints link
  to teams, so this contract should not silently bypass that decision.

# Human decisions or resources

- [ ] Confirm the public player key and whether it is the natural Basketball
      Reference ID, an internal surrogate, or both in different contexts.
- [ ] Choose the v1 player resources, route shapes, filters, pagination, and
      deterministic ordering.
- [ ] Decide which official-stat families and grains are public first: aggregate
      player-season, team stints, regular season, postseason, or a staged subset.
- [ ] Define how `source_team_code` values such as `2TM`/`3TM`/`4TM` appear in
      responses without becoming public teams, and how rows with missing stats
      are represented.
- [ ] Confirm how the settled F5-006 team identity and NBA season scope apply to
      player/team-season resources.

# Acceptance criteria

Not final — this card is not ready to start. Draft direction:

- `docs/architecture/API_CONTRACT.md` states the public player identity, route
  shapes, grain boundaries, season/postseason scope, and null/empty/404 rules.
- The contract preserves the official-stats separation rules and does not
  expose generated metrics as official stats.
- A follow-up implementation card can name the exact query repositories,
  schemas, routes, fixtures, and validation commands.

# Scope

Public API and read-only database contract research for players, player-season
relationships, and official `stats` tables, including the relevant architecture
and domain documents.

# Out of scope

Implementing player/statistics routes, changing core or stats schema, loading or
backfilling data, generating metrics, or contacting Basketball Reference.

# Impact

Potentially spans API schemas/services/routers, read-only query repositories,
the OpenAPI contract, and tests. The decision must preserve the raw/core/stats/
features boundaries and the regular-season/postseason separation.

# Implementation notes

Start from the already implemented database grains and the official mapping
documents. Do not choose a response shape from the wide table columns alone;
first decide which public resource a client is asking for and how stable player
and team identities connect to it.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — record the settled player and official
  stats contract in the later implementation card.
- `docs/domain/BUSINESS_RULES.md` — clarify any player/stint/statistics rule that
  the decision makes permanent.

# Review evidence

## Automated validation

- Command:
- Result:

## Manual happy path

1. Review the core player relationships and the regular/postseason stats table
   families.
2. Resolve the human decisions above, including the F5-006 dependency.
3. Verify that the resulting resources can be mapped to read-only queries and
   explicit Pydantic schemas.

Expected result: an implementation-sized, verifiable API task can be prepared.

## Manual sad path

1. Try to define one response that combines aggregate and team-stint rows.
2. Try to use `TOT` as a public team or to derive aggregate stats by summing
   stints.
3. Reject those shapes against the official stats contract.

Expected result: the unresolved boundaries are recorded instead of becoming
   accidental API behavior.

## Known limitations

- No player or statistics endpoint is implied until the contract decisions are
  answered.
