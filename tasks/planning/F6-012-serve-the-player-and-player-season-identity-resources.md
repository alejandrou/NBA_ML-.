---
id: F6-012
title: Serve the player and player-season identity resources
areas:
  - planning
  - api
  - database-read
  - testing
priority: 95
depends_on:
  - F6-004
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - src/nba_data/api/routers/teams.py
  - src/nba_data/api/services/teams.py
  - src/nba_data/api/schemas/teams.py
  - src/nba_data/db/repositories/queries/teams.py
  - src/nba_data/db/repositories/queries/seasons.py
  - src/nba_data/api/services/readiness.py
  - src/nba_data/db/models/core.py
validation: []
critical_actions: []
---

# Goal

Implement the first four route templates of the player contract — the identity
resources, which read `core` only and touch no `stats` table:

```text
GET /api/v1/players
GET /api/v1/players/{pid}
GET /api/v1/players/{pid}/seasons
GET /api/v1/players/{pid}/seasons/{season_year}
```

This is deliberately the half of the contract that is **not** gated on data
health. The `core.players`, `core.player_seasons`, and `core.player_team_seasons`
tables are current; only the `stats` families are stale, and they belong to
F6-013 and F6-014.

# Evidence and current state

- `docs/architecture/API_CONTRACT.md` now carries the settled Players and
  statistics section, written by F6-004. It fixes the key, the casing rule, the
  bodies, the ordering, the status codes, and the non-promises. Nothing in it is
  implemented.
- `db/repositories/queries/` holds `teams.py` and `seasons.py` only. There is no
  player query repository, player service, player schema, or player router.
- `routers/teams.py`, `services/teams.py`, `schemas/teams.py`, and
  `queries/teams.py` are the working four-layer example this card copies:
  router translates HTTP, service orchestrates, query repository reads, schema
  defines the body.
- `routers/teams.py:27-30` registers an explicit `GET /` returning 404 so an
  empty code segment does not fall through to the collection. The player routes
  need the same treatment for an empty `{pid}`.
- The readiness required-table list currently holds `core.teams` and
  `core.seasons` (`services/readiness.py`). This card adds the three `core`
  player tables to it, because a route whose table is not checked can still 500
  against a partially migrated database.

# Human decisions or resources

- [ ] Does `/players` enumerate every row in `core.players`, or only players
      that have at least one `core.player_seasons` row? The contract fixes the
      ordering and the envelope but does not say which set is enumerated, and
      the archive may hold players loaded without seasons.
- [ ] Does `/players/{pid}/seasons` list every `core.player_seasons` row, or
      only seasons that have at least one stint or one stat row? The contract's
      `teams` field tolerates an empty list, so both readings are consistent
      with it.
- [ ] Is `/players/{pid}/seasons` paginated with the standard envelope, or
      returned whole? A career is at most ~25 rows, so the envelope may be
      ceremony — but a bare list would be the first collection in v1 that does
      not use it.
- [ ] Confirm the `{pid}` path constraint. `core.players.basketball_reference_player_id`
      is `String(32)`; teams use `Path(min_length=1, max_length=10)`. Decide
      whether the route also rejects non-lowercase input at validation (422) or
      lets it fall through to the contract's 404.

# Acceptance criteria

To be completed when the decisions above are settled. In outline:

- A read-only `db/repositories/queries/players.py` with deterministic ordering,
  never mutating its Session.
- Pydantic schemas for the player object and the season-index item, matching the
  contract's bodies exactly and publishing no surrogate id, slug, or lineage
  column.
- A `players` router registered under `/api/v1`, with the exact-match casing
  rule and the contract's 404 detail strings.
- `core.players`, `core.player_seasons`, and `core.player_team_seasons` added to
  the readiness required-table list.
- The contract's "Specified, not yet served" marker updated to note that the
  identity resources are now served.
- Offline `TestClient` tests with dependency overrides, per
  `API_ARCHITECTURE.md`; no PostgreSQL required.

# Scope

`src/nba_data/api/routers/`, `src/nba_data/api/services/`,
`src/nba_data/api/schemas/`, `src/nba_data/db/repositories/queries/`,
`src/nba_data/api/services/readiness.py`, `tests/unit/`, and the marker
paragraph in `docs/architecture/API_CONTRACT.md`.

# Out of scope

Every statistics route and every `stats` table — those are F6-013 and F6-014.
The roster table. Any schema change or migration. Any write path. Name search.
Contacting Basketball Reference.

# Impact

- **API:** four new routes; the first `core.players` reads in the application.
- **Readiness:** three tables added to the required list.
- **Data:** none. Read-only.

# Implementation notes

Follow the teams resource layer for layer rather than inventing a shape. The
contract is the authority on bodies and status codes; do not re-derive them from
the ORM.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — narrow the "Specified, not yet served"
  marker to the statistics routes once these four are live.

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
