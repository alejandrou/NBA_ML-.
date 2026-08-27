---
id: F6-014
title: Serve the postseason aggregate and stint stat routes
areas:
  - planning
  - api
  - database-read
  - data-quality
  - testing
priority: 85
depends_on:
  - F6-004
  - F6-013
  - F4E-024
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - src/nba_data/db/models/stats.py
  - src/nba_data/validation/parser_contracts.py
validation: []
critical_actions:
  - Named, not authorized - the postseason families are stamped player-page-postseason-parser-v1 and are stale under parser_contracts.py. F4E-024's cache-only rebuild must land first; this card runs no backfill and the rebuild needs its own direct owner instruction.
---

# Goal

Complete the contract by serving the postseason half of the two statistics route
templates:

```text
GET /api/v1/players/{pid}/seasons/{season_year}/postseason/aggregate/{family}
GET /api/v1/players/{pid}/seasons/{season_year}/postseason/stints/{family}
```

across all eight families — `stats.player_postseason_{family}` for the aggregate
grain and `stats.player_team_postseason_{family}` for the stint grain. When this
lands, the "Specified, not yet served" marker leaves `API_CONTRACT.md` entirely.

# Evidence and current state

- The postseason tables carry the same eight column mixins as the regular ones,
  so F6-013's family schemas are reused unchanged. This card is deliberately the
  smallest of the three: it adds a `{season_type}` branch and two table
  families, not a new body shape.
- **Data health.** All 81,056 postseason rows in the persistent database are
  `player-page-postseason-parser-v1` and are stale under `parser_contracts.py`.
  Both postseason grains therefore wait on F4E-024's cache-only rebuild.
- Postseason stats live in their own tables by rule
  (`docs/domain/BUSINESS_RULES.md`, Postseason Stats) and must never be mixed
  into the regular families — the path segment is what keeps that true at the
  API boundary.

# Human decisions or resources

- [ ] Does a season with no postseason appearance return 404
      `Statistics not found` on the aggregate route, or is a distinct signal
      needed so a client can tell "did not make the playoffs" from "we have no
      data"? The contract gives one status code; whether that conflation is
      acceptable is a product decision.
- [ ] Confirm that F6-013's `{season_type}` dispatch generalizes as written, or
      record what has to change. This is verifiable only once F6-013 exists.
- [ ] Confirm the postseason stint family is populated well enough to serve, on
      the same evidence F4E-024 produces for the aggregate family.

# Acceptance criteria

To be completed when the decisions above are settled. In outline:

- The postseason branch of the routing table served, reusing F6-013's family
  schemas with no new body shape.
- No response mixes regular and postseason rows, and no regular route reads a
  postseason table.
- The served postseason `stats` tables added to the readiness required-table
  list.
- The "Specified, not yet served" marker removed from `API_CONTRACT.md`, since
  every route in the section is then live.
- Offline `TestClient` tests covering both postseason grains, including a
  multi-team postseason aggregate row.

# Scope

`src/nba_data/api/` (routers, services, schemas),
`src/nba_data/db/repositories/queries/`, the readiness required-table list,
`tests/unit/`, and the marker paragraph in `API_CONTRACT.md`.

# Out of scope

The roster table. Any write, load, backfill, or rebuild, including F4E-024's.
Any schema change. Generated metrics. Career or multi-season aggregation.
Contacting Basketball Reference.

# Impact

- **API:** the final sixteen served combinations; the contract is fully
  implemented.
- **Readiness:** the postseason `stats` tables join the required list.
- **Sequencing:** blocked on F6-013 for the shared schemas and on F4E-024 for
  data health.

# Implementation notes

If this card turns out to need a new body shape, that is evidence F6-013's
schemas were built per-dimension rather than per-family — say so rather than
duplicating them.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — remove the "Specified, not yet served"
  marker.

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
