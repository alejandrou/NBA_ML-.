---
id: F4E-021
title: Define what full_name means and drop the unused slug column
areas:
  - data-quality
  - database-schema
  - testing
  - documentation
priority: 35
depends_on:
  - F4E-020
read:
  - src/nba_data/db/repositories/core.py
  - src/nba_data/db/models/core.py
  - src/nba_data/scraping/parsers/team_season.py
  - src/nba_data/scraping/normalizers/team_season.py
  - docs/domain/BUSINESS_RULES.md
  - docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md
validation:
  - uv run pytest tests/unit/test_team_season_loader.py tests/unit/test_core_models.py tests/unit/test_offline_database_validation.py
  - uv run ruff check .
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Applying revision 0009 to a persistent or shared database requires explicit owner approval; authoring the reversible revision and running it against the disposable local lane does not.
  - Before the owner applies 0009 anywhere persistent, core.players.slug must be confirmed entirely NULL against that database. This card assumes it from code evidence only — no code in src/ has ever written the column.
  - Never edit migration 0001_initial_raw_core.py. Revision 0009 supersedes it by dropping the column 0001 created.
---

# Goal

Write down what `core.players.full_name` means, record that neither an alias
model nor a distinct player-page-name field is needed in v1, and drop
`core.players.slug` — an inert column whose only rebuild-stable generator would
duplicate an identifier the row already carries.

The owner's decisions on 2026-08-26 settle all four open questions. This card
implements them; it no longer decides anything.

# Evidence and current state

## What `full_name` actually holds

[`get_or_create_player`](../../src/nba_data/db/repositories/core.py#L152-L180):

```python
creation_name = name or player_id
...
if player is not None:
    if name and _is_fallback_or_empty(player.full_name, fallback=player_id):
        player.full_name = name
```

On creation the name is stored, falling back to the Basketball Reference id. On
every later encounter the stored name is **only** replaced if the existing value
is still the fallback. Read as code alone, `full_name` is *the first non-fallback
name any loader supplied*, and reloading the archive in a different order could
change it.

Read against the archive, it cannot. See the measurement below.

## The naming evidence, re-measured

The card's earlier evidence section was measured across every table on every
cached page, including tables no parser reads. Re-measuring against **the tables
the loader actually consumes** changes the answer completely.

`SUPPORTED_TEAM_SEASON_TABLES`
([`parsers/team_season.py:9-21`](../../src/nba_data/scraping/parsers/team_season.py#L9-L21))
is nine tables: `roster`, `totals_stats`, `per_game_stats`, `per_minute_stats`,
`per_poss`, `advanced`, `shooting`, `adj_shooting`, `pbp_stats`. Running the
repository's own `parse_team_season_page` → `normalize_team_season_page` over all
775 cached team pages and collecting every `player_name` that reaches
`get_or_create_player`:

| Measurement | Result |
|---|---|
| Team pages parsed | 775 |
| Distinct `basketball_reference_player_id` values | 2,551 |
| Player ids with **more than one** `player_name` | **0** |
| Rows carrying a player id but no `player_name` | **0** |

**Every player in this archive has exactly one candidate name.** `full_name` is
load-order dependent as a mechanism and deterministic as a value: no reload order
produces a different database.

## The player-page `<h1>` earns nothing

The original card asked whether the player-page `<h1>` deserves a distinct field.
Measured against the same 2,551 loader-visible players:

| Measurement | Result |
|---|---|
| Player pages carrying an `<h1>` | 2,551 |
| Players present in both the team pages and the player pages | 2,551 |
| Loader-visible players with no cached player page | 0 |
| Player pages with no loader row | 0 |
| **`<h1>` values differing from the stored `full_name`** | **0** |

The two sets coincide exactly and the strings match exactly — not after
accent-folding, but byte for byte. The `<h1>` is a second rendering of the value
already stored, so it earns neither a column nor an alias row.

## Where the 197 "varying" players actually came from

A raw scan across *all* tables, including ones no parser reads, finds 2,698
distinct player ids on team pages, of which 197 render under more than one
string. Every one of those 197 varies **only because of the `salaries2` table**.
Per-table consistency across the whole archive:

| Table | Players present | Players varying within the table |
|---|---|---|
| `roster` | 2,551 | 0 |
| the eight stats tables and their eight `_post` variants | 1,474 – 2,550 | 0 |
| **`salaries2`** | **2,647** | **55** |

`salaries2` is not in `SUPPORTED_TEAM_SEASON_TABLES` and no parser reads it. The
2,698 − 2,551 = 147 extra player ids it contributes are exactly the players with
no cached player page.

The card's earlier claim that the variation splits into *abbreviations* and
*transliterations* does not hold. There are **zero** abbreviation cases anywhere
in the archive — the cited examples `{"LeBron James", "L. James"}` and
`{"Victor Wembanyama", "V. Wembanyama"}` do not exist in it. The real split of
the 197 is 103 pure diacritic differences and 94 substantive ones, and all 197
live in the unread salary table.

## `salaries2` is what proves the retroactive re-rendering

The earlier framing said "no era-specific names were observed", which is an
absence of evidence. The salary table supplies the positive proof: it preserves
the era name while every table the loader reads shows the current one, **on the
same page**.

| Player id | `roster` and all stats tables | `salaries2` |
|---|---|---|
| `kanteen01` | Enes Freedom (on the 2012 UTA page) | Enes Kanter |
| `pendeje02` | Jeff Ayres (on the 2010 POR page) | Jeff Pendergraph |
| `walkebi01` | Henry Walker (on the 2009 BOS page) | Bill Walker |
| `hardati02` | Tim Hardaway Jr. | Tim Hardaway |
| `rebraze01` | Željko Rebrača | Zeljko Rebraca |

This is the constraint that decides the slug: a name-derived slug would change
under this archive on a re-scrape, because Basketball Reference rewrites the
name it prints for a past season. `artesro01` renders as "Metta World Peace"
everywhere, including the 2004 Indiana page, and no "Ron Artest" string exists in
the archive — that example was checked and holds.

## The inert column

`core.players.slug` is declared at
[core.py:89](../../src/nba_data/db/models/core.py#L89) and created by migration
`0001` at [line 112](../../alembic/versions/0001_initial_raw_core.py#L112).
Grepping `src/` for `slug` finds it **only** on that one model line; every other
hit is the unrelated cache-filename slug in `scraping/cache.py`. Nothing writes
it, nothing reads it, no API response carries it.

It is the same shape of defect as `core.teams.franchise_id` — but the disposition
differs deliberately, and the difference is the point. `franchise_id` was
withdrawn from the API and **left in the schema**
([API_CONTRACT.md:115](../../docs/architecture/API_CONTRACT.md#L115)) because a
loader could one day populate it with real lineage. `slug` has no such future:
its only rebuild-stable generator is `basketball_reference_player_id`, which the
row already carries, so populating it would store a second copy of an existing
identifier.

## What the drop touches

- [`db/models/core.py:89`](../../src/nba_data/db/models/core.py#L89) — the
  declaration.
- [`tests/unit/test_offline_database_validation.py:304-310`](../../tests/unit/test_offline_database_validation.py#L304-L310)
  hand-writes `create table core.players (... slug varchar(200))`. It is DDL
  typed out by hand, not reflected from the model, so it does **not** fail when
  the column goes — which is exactly why it must be updated deliberately rather
  than left to a test run to catch.

Nothing else. `test_migration_snapshots.py` pins named constraints, not columns;
`test_impact_map_documentation.py` parses only the `stats` table count.

# Human decisions or resources

- [x] **1. What is `core.players.full_name` defined to be?** **The current name
      as the source renders it.** The definition describes the data, not the load
      mechanism. Recorded together with the measurement that makes it safe: every
      player in this archive has exactly one candidate name, so the code's
      first-observed-name behavior cannot produce a different value under a
      different load order. (Owner, 2026-08-26.)
- [x] **2. Does anything need an alias model?** **No alias model in v1.** A
      `player_aliases` table would hold **zero rows** against this archive — not
      "only rendering variants". Every name that reaches the database is unique
      per player id. The question returns only if a source that renders
      era-specific names is added; the `salaries2` table is such a source and is
      deliberately not read. (Owner, 2026-08-26.)
- [x] **3. Should the fallback-to-id behavior stay?** **Yes — `full_name` stays
      `NOT NULL` and the id fallback stays.** It never fires: zero rows across
      775 team pages carry a player id without a name. It is documented as an
      unreached safety net and pinned by a test, because "unreached" is a
      property of today's archive rather than a guarantee. No migration. (Owner,
      2026-08-26.)
- [x] **4. Does `core.players.slug` get populated, dropped, or reserved?**
      **Dropped**, by a new reversible revision. The stability constraint was
      confirmed: a slug must survive a database rebuild, so it cannot derive from
      the surrogate `players.id`, and the retroactive re-rendering proven above
      rules out a normalized name. That leaves `basketball_reference_player_id`
      as the only stable candidate, which makes the column a duplicate of a value
      the row already has. F6-004 decides only whether the API *exposes* a slug,
      and now consumes "there is no slug column; the Basketball Reference id is
      the stable player key." (Owner, 2026-08-26.)
- [x] **5. Is a migration or backfill needed?** A migration, yes — revision
      `0009` for the column drop. **No backfill:** the definition of `full_name`
      is being written down, not changed, so no stored value moves. (Owner,
      2026-08-26.)

# Acceptance criteria

- A new Alembic revision `0009_drop_player_slug` exists with
  `down_revision = "0008_drop_raw_schema"`. Its `upgrade` drops
  `core.players.slug`; its `downgrade` recreates it as
  `sa.Column("slug", sa.String(length=200), nullable=True)`, matching `0001`
  exactly. The `downgrade -1` → `upgrade head` → `alembic check` round trip
  inside `bash scripts/validate_database.sh` passes clean.
- `alembic/versions/0001_initial_raw_core.py` is byte-identical to its current
  content: `git diff` over that path is empty.
- The `slug` declaration is gone from `src/nba_data/db/models/core.py`, and
  `grep -rn "slug" src/` returns hits only inside
  `src/nba_data/scraping/cache.py`, where the word means a cache filename part.
- `tests/unit/test_offline_database_validation.py` no longer creates a `slug`
  column in its hand-written `core.players` DDL.
- `docs/domain/BUSINESS_RULES.md`'s Players section states, with the same
  permanence as the player-identity rule it already carries:
  - `full_name` is **the current name as Basketball Reference renders it**;
  - every player in the cached archive has exactly one such name across all nine
    tables the loader reads, so the stored value does not depend on load order;
  - **there is no alias model in v1**, and the condition that would reopen the
    question is a source that renders era-specific names;
  - `full_name` is `NOT NULL` and falls back to
    `basketball_reference_player_id`, a path that no row in the cached archive
    reaches;
  - the player-page `<h1>` is the same string as the stored `full_name` for all
    2,551 players, so it is not a separate name and gets no field of its own.
- The existing retroactive-rendering rule at
  `docs/domain/BUSINESS_RULES.md:38-41` is upgraded from "no era-specific names
  were observed" to the positive finding: the unread `salaries2` table preserves
  era names while every table the loader reads shows the current name on the same
  page, which is what proves the re-rendering rather than merely failing to
  contradict it.
- `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md`'s DB-07 row is updated: the
  column's fate is no longer "deferred" but **dropped by revision 0009**, and the
  row points at this card for the column and at F6-004 for the API question only.
- `tasks/planning/F6-004-define-public-player-stats-api-contract.md`'s slug
  decision no longer waits on this card. It records that `core.players.slug` does
  not exist and that the only rebuild-stable player key is
  `basketball_reference_player_id`, so its remaining question is whether to
  expose that id under the name `slug` or under its own name.
- `tests/unit/test_team_season_loader.py` gains two tests:
  - **the reload-order case** — loading two batches that supply *different*
    non-fallback names for the same `basketball_reference_player_id` leaves
    `full_name` at the first one, asserted in both orders, pinning the documented
    behavior rather than an accident;
  - **the fallback-upgrade case** — a player first created with no name holds the
    id as `full_name`, and a later batch that does supply a name replaces it.
- `uv run pytest`, `uv run ruff check .`, and
  `uv run python scripts/validate_tasks.py` all pass.

# Scope

`alembic/versions/0009_drop_player_slug.py` (new),
`src/nba_data/db/models/core.py`,
`tests/unit/test_offline_database_validation.py`,
`tests/unit/test_team_season_loader.py`, `docs/domain/BUSINESS_RULES.md`,
`docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md`, and the slug decision in
`tasks/planning/F6-004-define-public-player-stats-api-contract.md`.

# Out of scope

`src/nba_data/db/repositories/core.py` — `get_or_create_player` is **not
changed**. The decision is to document what it does, not to alter it; a code
change here would be a contract change for no measured benefit.

Migration `0001`, which is never edited. `player_name_display` on the stats
tables, which F4E-019 settles as *the name as printed in this source row*.
Whether the API exposes a player slug at all, which is F6-004. Teaching any
parser to read `salaries2` — the salary table is a naming *source*, not a stats
source, and adding it is a separate decision with its own evidence. Team identity
and franchise lineage, which are F5-006 and F5-008. `core.teams.franchise_id`,
which keeps its own disposition. Applying any migration to a persistent database.

# Impact

- **Schema:** `core.players` loses `slug` once `0009` is applied. The column has
  never been written, so no runtime behavior changes and no data is lost.
- **Migrations:** the chain head moves from `0008_drop_raw_schema` to
  `0009_drop_player_slug`. This card is ordered after F4E-020 for that reason
  and no other; if F4E-020's numbering changes, re-read the head from the
  `revision:` string in the file rather than assuming.
- **API:** none today. `slug` was never served. F6-004 is unblocked with a
  settled input rather than a pending one.
- **Contract:** `full_name` acquires a written definition it did not have. The
  definition matches the value already stored, so no consumer sees a change.
- **Tests:** two added to `test_team_season_loader.py`; one fixture corrected in
  `test_offline_database_validation.py`.

# Implementation notes

The `full_name` definition is being **recorded, not changed**. Resist the pull to
"fix" `get_or_create_player` to match the definition more literally — for example
by overwriting on every encounter so the last loader wins. The measurement says
first-wins and last-wins produce identical databases against this archive, so
such a change would carry contract risk for no observable gain.

Write the `0009` downgrade by copying the column definition out of `0001`'s
`upgrade` verbatim, including `nullable=True` and `length=200`. A downgrade that
quietly changes either is a silent schema fork; the `downgrade -1` →
`upgrade head` → `alembic check` sequence in the disposable lane is what proves it
did not happen.

When editing `BUSINESS_RULES.md`, extend the existing Players section rather than
starting a new one. The rule "Do not use `player_name` as a stable key" stays
exactly as it is — the new `full_name` definition explains what the column
*means*, and does not promote it to an identifier.

The `salaries2` finding is the most reusable thing this card produces. Record it
where a future audit will hit it, so nobody re-opens the alias question by
scanning all tables on a page and rediscovering 197 "conflicts" that never reach
the database.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md` — the `full_name` definition, the measured
  one-name-per-player finding, the "no alias model in v1" decision with its
  reopening condition, the `NOT NULL` fallback and that it is unreached, and the
  `salaries2` evidence that positively proves retroactive re-rendering.
- `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md` — DB-07 resolved: the
  column is dropped, not deferred.

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
