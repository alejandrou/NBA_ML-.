---
id: F4E-023
title: Correct stale claims in the durable architecture documents
areas:
  - documentation
  - data-quality
priority: 55
depends_on: []
read:
  - docs/architecture/IMPACT_MAP.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - docs/validation/TEAM_SEASON_PIPELINE.md
  - src/nba_data/db/models/stats.py
validation:
  - uv run python scripts/validate_tasks.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Correct three durable documents that describe a system the repository no longer
is. Each states something an implementer would reasonably act on, and each is
false against the current model and database.

# Evidence and current state

## `IMPACT_MAP.md` overstates the stats schema by eleven tables

[IMPACT_MAP.md:155](../../docs/architecture/IMPACT_MAP.md#L155) reads:

> **Schemas:** `raw` (3 tables), `core` (7), `stats` (**44** wide tables in 4
> families).

Introspected from `Base.metadata`, the `stats` schema holds **33** tables, 16 of
them postseason. Summing `count(*)` over all 33 in the live `nba` database gives
306,392 rows. There is no set of 44. The `raw` (3) and `core` (7) counts are
correct.

The number matters because `IMPACT_MAP.md` is the document a task card consults
to size a schema change, and eleven phantom tables make every such estimate
wrong in the same direction.

## `TEAM_SEASON_PIPELINE.md` denies a pipeline that exists and is loaded

[TEAM_SEASON_PIPELINE.md:99](../../docs/validation/TEAM_SEASON_PIPELINE.md#L99) reads:

> There is no separate player-page pipeline yet. […] Dedicated Basketball
> Reference player pages remain future scope unless a later manifest and parser
> task explicitly adds them.

That pipeline shipped. `scraping/parsers/player_page.py`,
`normalizers/player_page.py`, `loaders/player_page_stats.py`,
`offline_player_stats_backfill.py`, and
`offline_player_postseason_stats_backfill.py` all exist, and the checked-in
reports record 2,515 player pages processed and 96,336 regular-season plus 81,056
postseason rows loaded from them.

The paragraph also predicts that when the path lands it "will own full
player-season aggregate rows for `stats.player_season_*`", which is now a
statement of fact rather than a plan, and should read that way.

## `OFFICIAL_STATS_SCHEMA.md` calls shipped tables "planned"

[OFFICIAL_STATS_SCHEMA.md:673](../../docs/architecture/OFFICIAL_STATS_SCHEMA.md#L673)
introduces the postseason player-season tables under "**Planned** postseason
player-season tables". All sixteen postseason tables exist, were created by
migration `0005_postseason_stats_tables`, and hold data. This is the schema
document of record, so "planned" here is the most load-bearing of the three
errors: a reader checking whether postseason storage exists is told no.

# Human decisions or resources

- None.

# Acceptance criteria

- `IMPACT_MAP.md` states the true `stats` table count, derived from the model
  rather than transcribed, and names the postseason subset.
- `TEAM_SEASON_PIPELINE.md` records that the player-page pipeline exists, names
  its modules, and states which tables it owns. The "Known Gaps" section keeps
  only gaps that are still gaps.
- `OFFICIAL_STATS_SCHEMA.md` describes the postseason family as existing, with
  the migration that created it, and no longer as planned.
- A test asserts the `stats` table count in `IMPACT_MAP.md` matches
  `Base.metadata`, so this specific number cannot drift again silently. Parse the
  number from the document; do not restate it in the test.
- No schema change, no migration, no data change.

# Scope

- `docs/architecture/IMPACT_MAP.md`
- `docs/validation/TEAM_SEASON_PIPELINE.md`
- `docs/architecture/OFFICIAL_STATS_SCHEMA.md`
- `tests/unit/` for the table-count assertion.

# Out of scope

Every other claim in these documents. This card fixes three measured errors; it
is not a documentation audit, and widening it would make it unreviewable. The
`2TM`/`3TM`/`4TM` enumerations these documents also carry belong to F4E-014.

# Impact

Documentation only. Removes three false premises that future cards would
otherwise inherit — the eleven phantom tables in particular have already been
cited in sizing arguments.

# Implementation notes

Fix the numbers by deriving them, not by editing digits. The table-count test is
the point of the card: two of these three errors are drift, and drift recurs
unless something asserts against the model.

Do not extend the test to the `raw` and `core` counts in the same line unless
they are equally cheap to derive — a test that is expensive to keep true gets
deleted.

# Durable knowledge updates

This card *is* a durable knowledge update. The three documents above are its
entire output, plus the test that holds one of them true.

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
