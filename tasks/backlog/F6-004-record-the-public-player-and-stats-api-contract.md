---
id: F6-004
title: Record the public player and official-stats API contract
areas:
  - api
  - database-read
  - data-quality
  - documentation
priority: 100
depends_on:
  - F5-005
  - F5-006
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/domain/BUSINESS_RULES.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/db/models/core.py
  - src/nba_data/db/models/stats.py
  - src/nba_data/domain/team_codes.py
validation:
  - uv run python scripts/validate_tasks.py
  - uv run pytest tests/unit/test_api_foundation.py tests/unit/test_impact_map_documentation.py
  - uv run ruff check .
  - uv run pytest
critical_actions:
  - Named, not authorized - the aggregate and postseason families this contract specifies are stamped player-page-parser-v1 in the persistent nba database and are 625 player-seasons short. F4E-024's cache-only rebuild must land before those routes serve data. This card writes documentation only and runs no backfill; the rebuild needs its own direct owner instruction.
---

# Goal

Write the public player and official-statistics contract into
`docs/architecture/API_CONTRACT.md` and `docs/domain/BUSINESS_RULES.md`, so that
the routes, the public player key, the four stat dimensions, and the
multi-team-marker rule are fixed before any code is written and cannot be decided
accidentally by a response shape copied out of a wide table.

This card ships **documentation and successor cards only**. It adds no route, no
schema, no query repository, and no test of application behavior. The owner's
decisions on 2026-08-27 settle every question the planning card carried; this
card records them.

# Evidence and current state

## What exists

- `core.players`, `core.player_seasons`, and `core.player_team_seasons` model a
  global player, its seasons, and its per-team stints
  ([`core.py:79-162`](../../src/nba_data/db/models/core.py#L79-L162)).
- The `stats` schema holds 33 wide tables: one roster table plus 32 stat tables
  in four dimensions by eight families
  ([`stats.py`](../../src/nba_data/db/models/stats.py)).
- The API serves health, readiness, teams, and seasons. There is no player query
  repository, player schema, stats query repository, or player route. The
  read-only query package holds exactly two modules,
  [`queries/teams.py`](../../src/nba_data/db/repositories/queries/teams.py) and
  [`queries/seasons.py`](../../src/nba_data/db/repositories/queries/seasons.py).
- `StatsRepository` ([`repositories/stats.py`](../../src/nba_data/db/repositories/stats.py))
  is the write path and exposes only `upsert_*`. The API never reads through it;
  `API_ARCHITECTURE.md` confines API reads to `db/repositories/queries/`.

## The four dimensions are already separate in storage

| Dimension | Table family | Grain FK | Carries `source_team_code` |
|---|---|---|---|
| regular / aggregate | `stats.player_season_*` | `core.player_seasons.id` | yes |
| postseason / aggregate | `stats.player_postseason_*` | `core.player_seasons.id` | yes |
| regular / team stint | `stats.player_team_season_*` | `core.player_team_seasons.id` | no |
| postseason / team stint | `stats.player_team_postseason_*` | `core.player_team_seasons.id` | no |

Each family carries an identical column set across dimensions, because all four
inherit the same eight column mixins (`_TotalsColumnsMixin` and its siblings at
[`stats.py:98-350`](../../src/nba_data/db/models/stats.py#L98-L350)). One
Pydantic body shape per family therefore serves all four dimensions, which is
what makes a route template carrying a `{season_type}` and a grain segment cheap
rather than a 32-schema explosion.

## What the player row can actually publish

`core.players` holds `id`, `basketball_reference_player_id`, `full_name`, and the
inert `slug`. There is no birth date, height, weight, position, or college on the
player: that data lives per stint on `stats.player_team_season_roster`, which is
a ninth table in the regular team-stint family only. A public player resource can
therefore publish an identity and a name, and nothing else, without inventing a
grain.

`basketball_reference_player_id` is `nullable=True` in the model but never null
in practice: `get_or_create_player`
([`repositories/core.py:152-179`](../../src/nba_data/db/repositories/core.py#L152-L179))
passes it through `_clean_required` and refuses an empty value, so every row is
written with one. This is the same gap `core.teams` had before F5-007's
`0007_team_bref_id_not_null`.

## Data health of the families this contract specifies

Measured against the persistent `nba` database and recorded in F4E-024: all
96,336 `stats.player_season_*` rows are `player-page-parser-v1`, and all 81,056
postseason rows are `player-page-postseason-parser-v1`. Both are `stale` under
[`parser_contracts.py`](../../src/nba_data/validation/parser_contracts.py) and
fail `validate_official_stats` today. The regular team-stint family is the only
one at a current identifier (`team-season-parser-v1`). The aggregate family is
also 625 player-seasons short until the F4E-024 rebuild runs.

This does not change the contract - it changes when three of the four dimensions
may be served, which is why the successor implementation cards, not this one,
depend on F4E-024.

## The marker rule this contract must not re-break

`is_multi_team_marker` ([`domain/team_codes.py`](../../src/nba_data/domain/team_codes.py))
owns the rule for every layer: a numeric team count of at least two followed by
`TM`, open-ended. The cached archive already contains a `5TM` season
(`jonesbo02`, 2007-08), so a contract that enumerated `2TM`/`3TM`/`4TM` would be
wrong on the day it published. `TOT` is handled separately and is not a marker.

## Settled inputs this card consumes

- **F5-006 / F5-007 (done):** a public team is a code-era identity keyed by
  `basketball_reference_team_id`; `franchise_id` is withdrawn; the teams
  collection is not league-scoped. Player stints link to team codes and promise
  no lineage.
- **F5-005 (done):** seasons are permanently NBA-scoped and `season_year` is the
  public season key.
- **F4E-021 (settled 2026-08-26, in `tasks/backlog/`):** `core.players.slug` is
  dropped, and the only rebuild-stable slug source would have been
  `basketball_reference_player_id` itself. It is deliberately **not** in
  `depends_on`: this card states what v1 publishes, not what the schema holds, so
  the contract text is true before and after that migration lands.
- **F4E-019 (done):** `player_name_display` means *the name as printed in this
  source row*, `NULL` where the source prints none - populated on 8 of the 32
  stat tables, `NULL` by design on the other 24.

# Human decisions or resources

- [x] **1. What is the public player key?** **`basketball_reference_player_id`,
      alone.** Matched exactly, in the lowercase form Basketball Reference
      renders (`jamesle01`), the way team codes are matched exactly in uppercase.
      The surrogate `core.players.id` stays private, for the reason F5-006 gave
      for `core.teams.id`: it is stable within one database and not reproducible
      across a rebuild, so publishing it would hand clients a second key the
      contract then has to warn them off. The contract also states that the id is
      **required on every published row** - a player without one is a data
      defect, not a served possibility. (Owner, 2026-08-27.)
- [x] **2. Does the player resource expose a `slug`?** **No.** F4E-021 measured
      that the only rebuild-stable slug source is
      `basketball_reference_player_id`, which the response already carries, so
      "expose a slug" and "expose the Basketball Reference id" were one decision
      wearing two names. v1 publishes the id under its own name and no alias.
      (Owner, 2026-08-27.)
- [x] **3. What are the v1 routes?** **Nested under the player**, with grain and
      season type in the path rather than in a query parameter, so no request can
      ask for a shape that mixes them. Six route templates, listed under
      Acceptance criteria. Pagination, ordering, and the collection envelope
      follow the existing contract unchanged. (Owner, 2026-08-27.)
- [x] **4. Which families and grains are public in v1?** **All four dimensions,
      all eight families** - 32 tables, the complete stat model. Writing the
      contract once avoids a client-visible reshape later. Serving is staged by
      data health, not by contract: the successor cards for the aggregate and
      postseason dimensions depend on F4E-024's rebuild. The ninth table,
      `stats.player_team_season_roster`, is **out of v1** and named as a
      deliberate non-promise: it is regular-stint-only and carries biography
      rather than statistics, so publishing it is its own additive decision.
      (Owner, 2026-08-27.)
- [x] **5. How do multi-team markers appear?** **As `source_team_code` verbatim
      plus a derived `is_multi_team` boolean**, on aggregate rows only, and never
      as a team link. `is_multi_team` is computed by `is_multi_team_marker`, the
      one implementation of the semantic rule; the contract states the rule as a
      numeric count of at least two followed by `TM` and **never enumerates the
      set** - the archive's `5TM` season is the standing proof that an
      enumeration would be wrong. (Owner, 2026-08-27.)
- [x] **6. Does the API expose `player_name_display`?** **No.** It is `NULL` by
      design on 24 of the 32 stat tables, so exposing it would publish a field
      that is present in one dimension and empty in three, which reads as missing
      data rather than as source semantics. `core.players.full_name` is the only
      name the API publishes. (Owner, 2026-08-27.)
- [x] **7. How does the settled team and season scope apply?** **Answered by
      F5-005 and F5-006.** Stints reference the code-era identity by
      `basketball_reference_team_id` and promise no lineage; seasons keep their
      permanent NBA scope. Every player resource inherits the season scope and
      states so explicitly, because the two scopes deliberately disagree.
      (Settled before this card.)

# Acceptance criteria

## `docs/architecture/API_CONTRACT.md` gains a Players and Statistics section

It is added after Seasons, and opens with an explicit **"Specified, not yet
served"** marker naming the successor cards, so no reader mistakes it for a
description of running routes. The successor that implements each resource
removes that resource from the marker.

The section states all of the following.

- **Player identity.** `basketball_reference_player_id` is the permanent v1
  player key, matched exactly in the source's own casing;
  `/api/v1/players/JAMESLE01` is not `/api/v1/players/jamesle01` and returns 404.
  `core.players.id` is private. No `slug` is published, and the reason: its only
  rebuild-stable source would be the key the response already carries. The key is
  required on every published row.
- **The six route templates**, with `{pid}` the player key, `{season_type}` one
  of `regular` or `postseason`, and `{family}` one of `totals`, `per_game`,
  `per_minute`, `per_poss`, `advanced`, `shooting`, `adj_shooting`, `pbp`:

  ```text
  GET /api/v1/players
  GET /api/v1/players/{pid}
  GET /api/v1/players/{pid}/seasons
  GET /api/v1/players/{pid}/seasons/{season_year}
  GET /api/v1/players/{pid}/seasons/{season_year}/{season_type}/aggregate/{family}
  GET /api/v1/players/{pid}/seasons/{season_year}/{season_type}/stints/{family}
  ```

- **The dimension routing table**, so a path maps to exactly one table family:
  `regular/aggregate` to `stats.player_season_{family}`, `postseason/aggregate`
  to `stats.player_postseason_{family}`, `regular/stints` to
  `stats.player_team_season_{family}`, `postseason/stints` to
  `stats.player_team_postseason_{family}`.
- **Response bodies.** The player object is
  `{"basketball_reference_player_id", "full_name"}`. A season-index item is
  `{"season_year", "league", "teams"}`, where `teams` is the list of
  `basketball_reference_team_id` values from `core.player_team_seasons`,
  documented as stint *membership* from `core` and never as a substitute for
  stint statistics. An aggregate stat object carries `season_year`,
  `season_type`, `source_team_code`, `is_multi_team`, and the family's stat
  columns. A stint stat object carries `season_year`, `season_type`,
  `basketball_reference_team_id`, and the family's stat columns.
- **Stat column names are the stored names**, verbatim and unrenamed (`fg_pct`,
  `fg3a`, `mp`, `tpl_dbl`), because they are the documented Basketball Reference
  mapping. A missing stat is `null` - never `0`, and never an omitted key.
- **Rates are JSON numbers.** `Numeric(10, 4)` columns publish as JSON numbers at
  their stored scale (`0.4661`), not as strings. This is stated because Pydantic
  serializes `Decimal` to a string in JSON mode by default, so a schema that
  types these columns as `Decimal` and is left unconfigured breaks the rule
  silently.
- **Lineage columns are private.** `source_url`, `cache_path`, `parser_version`,
  `created_at`, and `updated_at` are never published on any route.
- **Multi-team markers.** `source_team_code` is verbatim source metadata on
  aggregate rows and is nullable. `is_multi_team` is true when the code is a
  numeric team count of at least two followed by `TM`; the contract states the
  rule semantically and enumerates nothing. When it is true the value is not a
  team and resolves to no `/api/v1/teams` resource; when it is false the value is
  a real team code that does. Clients branch on the boolean, never on the string.
  `TOT` is not a multi-team marker, is never a team, and must not appear in this
  field at all - if it does, that is a data defect rather than a served shape.
- **Grain and derivation rules.** No response mixes aggregate and stint rows. The
  API computes nothing: every published number is a stored official value, never
  a sum of stints, never an averaged percentage, and never a generated metric
  from `features`.
- **Season scope.** Every player resource inherits the permanent NBA scope of
  `/api/v1/seasons` and introduces no `league` path or query dimension. Team
  references are code-era identities and carry no franchise lineage - the
  asymmetry between NBA-scoped seasons and league-agnostic teams is restated here
  rather than left to be inferred.
- **Ordering and pagination.** `/players` orders by
  `full_name ASC, basketball_reference_player_id ASC`; `/players/{pid}/seasons`
  by `season_year DESC`; stint collections by `basketball_reference_team_id ASC`.
  All collections use the existing envelope and the existing `page` / `page_size`
  bounds.
- **Status codes**, as a table: unknown player is 404 `Player not found`; a known
  player with no such season is 404 `Player season not found`; an existing
  player-season with no row in that dimension and family is 404
  `Statistics not found` for the aggregate routes, and 200 with an empty `items`
  list for the stint collections; an unrecognized `{season_type}` or `{family}`
  is 422 from path validation; a non-integer `{season_year}` is 422. Detail
  strings are fixed and never interpolate a cause.
- **Readiness impact.** The section names the tables each new resource adds to
  the readiness required-table list: `core.players`, `core.player_seasons`,
  `core.player_team_seasons`, and the `stats` tables the served routes read.
- **Named v1 non-promises**, each with its reason: no name search or filter on
  `/players` beyond pagination (`player_name` is not a stable key, and search is
  its own design); no `stats.player_team_season_roster` and therefore no
  biography fields; no `player_name_display`; no `slug`; no surrogate ids; no
  lineage columns; no career or multi-season totals, which would be a derived
  aggregate the storage does not hold; no cross-player, season-wide stat
  collection or leaderboard.

## `docs/domain/BUSINESS_RULES.md`

- The Players section states that `basketball_reference_player_id` is the public
  API key as well as the internal stable identifier, and that no other player
  identifier is published.
- The Source Team Codes and Trades section states that a multi-team marker is
  publishable as source metadata but is never a public team and never resolves to
  a team resource - the rule that already governs storage, now stated for
  publication too.
- No existing rule is weakened, and the `TOT` and marker rules keep their present
  wording.

## Successor cards

Three cards exist in `tasks/planning/`, each naming the part of the contract it
implements, with `depends_on` wired in this order:

- `F6-012` - players and player-season identity resources (route templates one
  through four). `depends_on: [F6-004]`.
- `F6-013` - regular-season aggregate and stint stat routes.
  `depends_on: [F6-004, F6-012, F4E-024]`.
- `F6-014` - postseason aggregate and stint stat routes.
  `depends_on: [F6-004, F6-013, F4E-024]`.

Each carries the F4E-024 data-health note where it applies and leaves its own
open questions as `- [ ]` items rather than pretending to be ready.

## Validation

`uv run python scripts/validate_tasks.py`, `uv run ruff check .`, and
`uv run pytest` all pass. No application behavior changes, so no test changes;
`tests/unit/test_api_foundation.py` still asserts the current four-route
unversioned set and the `/api/v1` prefix rule, unaffected by a documentation
card.

# Scope

`docs/architecture/API_CONTRACT.md`, `docs/domain/BUSINESS_RULES.md`, and three
new planning cards under `tasks/planning/`.

# Out of scope

Any code under `src/`, any test, any schema or migration, any route, any query
repository, any Pydantic schema, and the readiness required-table list itself -
that list changes when a route lands, not when its contract is written. Loading,
backfilling, or rebuilding data, including F4E-024's rebuild. Generated metrics
and the `features` schema. Publishing the roster table. Contacting Basketball
Reference.

# Impact

- **Documents:** `API_CONTRACT.md` gains its largest section; `BUSINESS_RULES.md`
  gains two clarifications.
- **API:** none today. The contract fixes the shape of three future cards.
- **Data:** none. The card writes no row and reads no database.
- **Sequencing:** F6-013 and F6-014 become gated on F4E-024, because three of the
  four dimensions are stale in the persistent database and 625 player-seasons are
  missing from the aggregate family.

# Implementation notes

Write the section against the models, not against this card's summaries - the
column lists in `src/nba_data/db/models/stats.py` are the authority for what a
family contains, and the eight shared mixins are the reason one body shape per
family serves all four dimensions.

Do not restate the collection envelope, the error taxonomy, or the pagination
bounds; they already exist earlier in `API_CONTRACT.md` and the new section
inherits them by reference. Duplicating them creates a second place to drift.

State the marker rule in the same words the domain module and
`BUSINESS_RULES.md` already use. New phrasing invites a future reader to treat it
as a separate rule with a separate set.

One inconsistency is worth knowing about while writing, and is **not** this
card's to fix: `OFFICIAL_STATS_SCHEMA.md`'s Player Name Display Semantics section
still cites 207 players with multiple renderings and the example
`{"LeBron James", "L. James"}`, which F4E-021 re-measured and found does not
exist in the archive - the variation comes entirely from the unread `salaries2`
table. This contract does not publish `player_name_display`, so the stale
measurement cannot leak into the API. Leave that text to F4E-021, which owns it.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` - the settled player and official-stats
  contract, marked as specified and not yet served.
- `docs/domain/BUSINESS_RULES.md` - the public player key, and that a multi-team
  marker may be published as metadata but never as a team.

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
