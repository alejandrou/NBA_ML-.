---
id: F6-013
title: Serve the regular-season aggregate and stint stat routes
areas:
  - planning
  - api
  - database-read
  - data-quality
  - testing
priority: 90
depends_on:
  - F6-004
  - F6-012
  - F4E-024
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/db/models/stats.py
  - src/nba_data/domain/team_codes.py
  - src/nba_data/validation/parser_contracts.py
validation: []
critical_actions:
  - Named, not authorized - this card serves data that F4E-024's cache-only rebuild must produce first. It runs no backfill of its own, and the rebuild needs its own direct owner instruction.
---

# Goal

Implement the regular-season half of the two statistics route templates:

```text
GET /api/v1/players/{pid}/seasons/{season_year}/regular/aggregate/{family}
GET /api/v1/players/{pid}/seasons/{season_year}/regular/stints/{family}
```

across all eight families — `stats.player_season_{family}` for the aggregate
grain and `stats.player_team_season_{family}` for the stint grain.

# Evidence and current state

- `docs/architecture/API_CONTRACT.md` fixes the dimension routing table, the
  body shape, the `is_multi_team` derivation, the null and JSON-number rules,
  the ordering, and the split status codes (404 for a missing aggregate row, 200
  with an empty `items` list for an empty stint collection).
- All four dimensions inherit the same eight column mixins
  (`src/nba_data/db/models/stats.py`), so one Pydantic body per family serves
  this card and F6-014. Building the family schemas here is what makes F6-014
  small.
- **Data health.** The regular stint family is the only one of the four at a
  current parser identifier (`team-season-parser-v1`). All 96,336
  `stats.player_season_*` rows in the persistent database are
  `player-page-parser-v1`, which `parser_contracts.py` classifies as stale, and
  the aggregate family is 625 player-seasons short. F4E-024's cache-only rebuild
  is therefore a hard dependency of the aggregate route, not a nicety.
- `StatsRepository` is the write path and exposes only `upsert_*`.
  `API_ARCHITECTURE.md` confines API reads to `db/repositories/queries/`, so
  this card adds a read-only module there rather than reusing it.

# Human decisions or resources

- [ ] How are the eight families dispatched — one route with a `{family}` path
      enum and a table/schema lookup, or eight generated route registrations?
      The first keeps the router small; the second gives OpenAPI a distinct,
      fully typed response model per family. Both satisfy the contract.
- [ ] Does the aggregate route serve a row whose `parser_version` is stale under
      `parser_contracts.py`, or does staleness make it invisible? The contract
      is silent, and this decides whether the route is safe to ship before
      F4E-024 completes in the persistent database.
- [ ] Confirm the Pydantic configuration that publishes `Numeric(10, 4)` as a
      JSON number rather than a string, and settle whether that is a shared base
      model config or per-field. The contract states the rule; it does not pick
      the mechanism.
- [ ] Should `/stints/{family}` include a stint whose `core.player_team_seasons`
      row exists but whose stat row is missing, as an entry with null stats, or
      omit it entirely? The contract fixes the empty-collection case, not the
      partial one.

# Acceptance criteria

To be completed when the decisions above are settled. In outline:

- A read-only stats query module under `db/repositories/queries/`, reading the
  `stats.player_season_*` and `stats.player_team_season_*` families by the
  contract's routing table.
- One Pydantic body per family, reused unchanged by F6-014, publishing the
  stored column names verbatim and no lineage column.
- `is_multi_team` derived through `is_multi_team_marker`, never by a local
  string test and never by an enumerated marker set.
- The contract's status codes exactly: 404 `Statistics not found` for a missing
  aggregate row, 200 with an empty `items` list for an empty stint collection,
  422 for an unrecognized `{family}`.
- The served `stats` tables added to the readiness required-table list.
- Offline `TestClient` tests covering a multi-team aggregate row, a null-heavy
  old season, and a rate column asserted to serialize as a JSON number.

# Scope

`src/nba_data/api/` (routers, services, schemas),
`src/nba_data/db/repositories/queries/`, the readiness required-table list,
`tests/unit/`, and the marker paragraph in `API_CONTRACT.md`.

# Out of scope

Postseason routes (F6-014). The roster table. Any write, load, backfill, or
rebuild, including F4E-024's. Any schema change. Generated metrics. Contacting
Basketball Reference.

# Impact

- **API:** sixteen served combinations (two grains × eight families).
- **Readiness:** the served `stats` tables join the required list.
- **Sequencing:** blocked on F4E-024 for the aggregate grain's data health.

# Implementation notes

The contract, not the ORM, is the authority on what a body contains.
`src/nba_data/db/models/stats.py` is the authority on which columns a family
has. Do not restate the collection envelope or the error taxonomy.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — narrow the "Specified, not yet served"
  marker to the postseason routes.

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
