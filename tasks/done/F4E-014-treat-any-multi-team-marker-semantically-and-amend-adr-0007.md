---
id: F4E-014
title: Treat any multi-team marker semantically and amend ADR 0007
areas:
  - scraping
  - data-quality
  - database-schema
  - documentation
  - testing
priority: 85
depends_on:
  - F4E-013
read:
  - docs/decisions/0007-handle-tot-and-trades.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/scraping/normalizers/player_page.py
  - src/nba_data/scraping/loaders/player_page_stats.py
  - src/nba_data/validation/official_stats.py
  - src/nba_data/db/models/core.py
  - src/nba_data/db/repositories/core.py
  - src/nba_data/validation/offline_database.py
validation:
  - uv run pytest tests/unit/test_team_codes.py
  - uv run pytest tests/unit/test_player_page_normalizer.py
  - uv run alembic check
  - uv run ruff check .
  - uv run pytest
critical_actions:
  - Tightening the four core check constraints requires a new reversible Alembic revision; applying it to a persistent database requires explicit owner approval.
  - Never edit an existing migration; supersede it with a new revision.
---

# Goal

Replace three independently hard-coded literal sets of multi-team markers with
one shared semantic predicate meaning **"numeric team-count marker with a count
of at least 2"**, and amend ADR 0007 so the accepted decision stops enumerating
`2TM`/`3TM`/`4TM`. The code is not deviating from the ADR — it faithfully
implements an ADR that is itself incomplete, so the ADR is part of the defect.

# Evidence and current state

## The marker set is hard-coded in three enforcement layers

| Layer | Site | Literal |
|---|---|---|
| Normalizer | [player_page.py:11](../../src/nba_data/scraping/normalizers/player_page.py#L11) | `MULTI_TEAM_CODES = frozenset({"2TM", "3TM", "4TM"})` |
| Loader | [player_page_stats.py:239](../../src/nba_data/scraping/loaders/player_page_stats.py#L239) | `if team_abbreviation.upper() in {"TOT", "2TM", "3TM", "4TM"}` |
| Validator | [official_stats.py:34-35](../../src/nba_data/validation/official_stats.py#L34) | `_SYNTHETIC_TEAM_CODES`, `_ALLOWED_AGGREGATE_SOURCE_CODES` |

Three layers, three literals, no shared source. Adding a marker means finding
all three.

## A further eleven sites guard `TOT` alone, so a numeric marker passes them all

The three above are where the *enumeration* lives. They are not the whole
enforcement surface. Every site below rejects the string `TOT` and nothing else,
so any `5TM` value that reaches it is treated as an ordinary team code — which is
the outcome ADR 0007 forbids. Found by searching the repository for `TOT`:

| Site | Guard |
|---|---|
| [team_season.py:123](../../src/nba_data/validation/team_season.py#L123) | `_tot_issues` returns early unless `team_abbreviation == "TOT"` |
| [core.py:50](../../src/nba_data/db/repositories/core.py#L50) | `get_or_create_team` rejects `TOT` |
| [core.py:87](../../src/nba_data/db/repositories/core.py#L87) | `get_or_create_team_alias` rejects `TOT` |
| [core.py:125](../../src/nba_data/db/repositories/core.py#L125) | `get_or_create_team_season` rejects `TOT` |
| [offline_processor.py:325](../../src/nba_data/scraping/offline_processor.py#L325) | `_normalize_team_abbreviation` rejects `TOT` |
| [offline_stats_backfill.py:192](../../src/nba_data/scraping/offline_stats_backfill.py#L192) | same check, second copy |
| [cache_inventory.py:150](../../src/nba_data/scraping/cache_inventory.py#L150) | inventory marks `TOT` sources invalid |
| [team_season.py:109,128,154](../../src/nba_data/scraping/loaders/team_season.py#L109) | batch and row-level `TOT` classification |
| [team_season_stats.py:838,852,1065](../../src/nba_data/scraping/loaders/team_season_stats.py#L838) | aggregate-vs-stint routing on `TOT` |
| [offline_database.py:396-408](../../src/nba_data/validation/offline_database.py#L396) | Phase 4D validator counts `TOT` rows only |
| [models/core.py:30,34,54,99](../../src/nba_data/db/models/core.py#L30) | four `CheckConstraint`s, each `<> 'TOT'` |

The database constraints are the load-bearing ones: `ck_core_teams_bref_id_not_tot`
and its three siblings are the last line of defence, and they would happily accept
a team row keyed `5TM`.

Note the constraints cannot call a Python predicate. They need a SQL expression,
which means the semantic rule has to be expressed twice — once in
`domain/team_codes.py` and once as a check constraint — with a test asserting the
two agree. That is the awkward part of this card and should be planned for rather
than discovered.

## The rule is also enumerated in six durable documents

Changing the code without these leaves the specification contradicting it:

- [`docs/decisions/0007-handle-tot-and-trades.md`](../../docs/decisions/0007-handle-tot-and-trades.md) lines 9, 10, 16, 18
- [`docs/architecture/OFFICIAL_STATS_SCHEMA.md`](../../docs/architecture/OFFICIAL_STATS_SCHEMA.md) lines 52, 116, 147, 154, 156
- [`docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`](../../docs/architecture/PLAYER_PAGE_STATS_MAPPING.md) lines 28, 34, 38, 45, 72, 77
- [`docs/domain/BUSINESS_RULES.md`](../../docs/domain/BUSINESS_RULES.md) lines 17, 31
- [`docs/architecture/IMPACT_MAP.md`](../../docs/architecture/IMPACT_MAP.md) line 114
- [`docs/validation/TEAM_SEASON_PIPELINE.md`](../../docs/validation/TEAM_SEASON_PIPELINE.md) line 48

`tasks/planning/F6-004` line 56 enumerates them too, but it is a card rather than
a durable document; it is corrected there rather than here.

## `5TM` exists in the cache today, and the loader lets it through

Measured over the 2,551 cached player pages, counting distinct
`(player, season)` pairs whose source team cell matches `^\d+TM$`:

| Marker | Distinct player-seasons | Raw row occurrences |
|---|---|---|
| `2TM` | 1,695 | 13,402 |
| `3TM` | 110 | 870 |
| `4TM` | 4 | 30 |
| `5TM` | **1** | 8 |

The single `5TM` is **Bobby Jones (`jonesbo02`), 2007-08**. No `0TM` and no
`1TM` appear anywhere in the cache.

## This has already cost data, and the loss is confirmed in the database

Two distinct failures follow from the enumeration, and the first is **measured,
not hypothetical**:

1. **The aggregate row is silently dropped at the normalizer.** Running
   `normalize_player_page_regular_season` over the cached `jonesbo02` page
   selects **0 rows** for season 2008: because `5TM` is not in
   `MULTI_TEAM_CODES`, `_select_full_season_row` never recognizes it as the
   full-season row, so the season yields nothing at all.

   Confirmed against the live `nba` database: `jonesbo02` / 2008 has a
   `core.player_seasons` row with **0 rows in `stats.player_season_totals` and 0
   in `stats.player_postseason_totals`**. It is one of the 634 player-seasons
   with no regular-season aggregate stats. This is real, persisted data loss
   caused by the literal set.

2. **The loader guard cannot catch a `5TM` that reaches it.** The check at
   [player_page_stats.py:239](../../src/nba_data/scraping/loaders/player_page_stats.py#L239)
   tests membership in `{"TOT", "2TM", "3TM", "4TM"}`, so a `5TM` value arriving
   as a stint `team_abbreviation` would pass through to
   `_resolve_player_team_season_id` as if it were a real team — the exact outcome
   ADR 0007 forbids: "synthetic source codes must never create `core.teams`,
   `core.team_seasons`, or `stats.player_team_season_*` rows." Fixing only the
   normalizer would leave this latent.

## Why the predicate is not just `^\d+TM$`

A bare `^\d+TM$` accepts `0TM` and `1TM`, neither of which is a multi-team
marker: a one-team season is a real stint, and a zero-team season is nonsense.
The census above shows the archive only ever uses counts of 2 or more, so the
predicate must mean *count ≥ 2*, not *any digits*. Leading-zero forms such as
`02TM` must also be rejected rather than silently parsed as 2.

## Why the predicate does not live in `scraping/`

`src/nba_data/validation/` currently imports only from `nba_data.validation` and
`nba_data.db`. Importing a predicate from `nba_data.scraping` would create a new
layering edge from validation to scraping that does not exist today.

# Human decisions or resources

- None.

# Acceptance criteria

- A new neutral module `src/nba_data/domain/team_codes.py` exposes one predicate
  for "is a multi-team marker" and, where a count is needed, one parser for the
  team count. It imports nothing from `scraping/`, `validation/`, or `db/`.
- The predicate accepts `2TM`, `3TM`, `4TM`, `5TM`, and any higher count, and
  rejects `0TM`, `1TM`, `02TM`, `TM`, `2TMX`, `TOT`, and every real team code.
- All three call sites above use it; no literal marker set remains in
  `normalizers/player_page.py`, `loaders/player_page_stats.py`, or
  `validation/official_stats.py`.
- **Every `TOT`-only guard in the eleven-site table rejects any multi-team marker
  too**, so a `5TM` value cannot be written as a team, an alias, or a team-season
  anywhere in the codebase.
- The four `core` check constraints reject multi-team markers as well as `TOT`,
  via a new Alembic revision. A test asserts the SQL constraint and
  `domain/team_codes.py` agree on the same inputs, since the rule is necessarily
  expressed in both.
- A regression test loads the Bobby Jones 2007-08 `5TM` row and asserts it is
  **skipped as a stint** with the existing `invalid_team_stint_source_team_code`
  reason, and **accepted as a full-season aggregate source row**, per ADR 0007.
  The normalizer must select 8 aggregate rows for that season where it currently
  selects 0.
- A second regression test drives `5TM` at the **core writer** and the **Phase 4D
  and 4E validators** — `get_or_create_team`, `get_or_create_team_alias`,
  `get_or_create_team_season`, `_tot_issues`, and the offline-database TOT count —
  asserting each rejects or reports it exactly as it does `TOT`. Without this the
  eleven sites are changed but unproven.
- `TOT` keeps its distinct handling: it is ignored for supported stats, not
  treated as a multi-team marker.
- ADR 0007 is amended to state the rule semantically rather than by enumeration,
  with a dated amendment note preserving the original decision text.
- All six durable documents listed above state the rule semantically. No document
  left in the repository enumerates `2TM`/`3TM`/`4TM` as the closed set.
- The parser-version constants are bumped to **`-v3`** (`player-page-parser-v3`,
  `player-page-postseason-parser-v3`), not reusing F4E-013's `-v2`.
- No database writes, no migration, no backfill run as part of this card.

# Scope

- New `src/nba_data/domain/` package and `team_codes.py`.
- The three enumeration call sites listed above.
- The eleven `TOT`-only guard sites listed above:
  `validation/team_season.py`, `db/repositories/core.py`,
  `scraping/offline_processor.py`, `scraping/offline_stats_backfill.py`,
  `scraping/cache_inventory.py`, `scraping/loaders/team_season.py`,
  `scraping/loaders/team_season_stats.py`, `validation/offline_database.py`.
- `src/nba_data/db/models/core.py` and a new Alembic revision — the four check
  constraints.
- The six durable documents listed above, plus
  `docs/decisions/0007-handle-tot-and-trades.md`.
- The two parser-version constants.
- `tests/unit/` for the predicate, the Bobby Jones regression, the core-writer
  and validator regressions, and the constraint-agreement test.

# Out of scope

The century fix, which is F4E-013. Repairing already-persisted rows. Deciding
what the API does with a multi-team marker, which belongs to F6-004. Any change
to how `TOT` is treated.

# Impact

Player-page normalization, player-page stats loading, and the Phase 4E official
stats validator all change their notion of a multi-team marker. ADR 0007 changes
from an enumeration to a rule. `parser_version` strings change again, so lineage
filters must expect `-v3`.

# Implementation notes

Emitting `-v3` here rather than `-v2` is deliberate: F4E-013 and this card change
different aspects of the same parsed output, and distinct labels keep each
card's contract attributable in stats lineage.

**The merge order is fixed, not free.** This card declares `depends_on: F4E-013`,
so the only safe order is F4E-013 (`-v2`) then this card (`-v3`). An earlier
revision claimed the two could merge in either order; that was wrong — merging
this card first would emit `-v3` and then F4E-013 would overwrite the constants
with `-v2`, downgrading the label while adding a fix. If the order is ever
reversed deliberately, the version constants must be reconciled by hand rather
than left to whichever card lands last.

The `5TM` row is a *confirmed live defect*, not a hypothetical hardening. Treat
the regression test as the point of the card.

**This card is large, and splitting it is legitimate.** An earlier revision
scoped it to three call sites, which was an undercount: the enforcement surface
is fourteen code sites, four database constraints, and six documents. If it
proves unwieldy, the natural seam is between the *behavioral* change (the
predicate and the three enumeration sites, which recover Bobby Jones's season)
and the *hardening* change (the eleven `TOT`-only guards and the constraints,
which prevent a future `6TM` from being written as a team). The first is what the
audit found; the second is what stops it recurring. Split there, not by layer,
and keep the parser-version bump with the behavioral half.

Note that a marker with count ≥ 2 is valid as an **aggregate** `source_team_code`
and invalid as a **stint** `team_abbreviation`. The predicate is shared; the
decision each layer makes with it is not.

# Durable knowledge updates

- `docs/decisions/0007-handle-tot-and-trades.md` — amend to the semantic rule.
- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — record the measured marker
  census and that the archive contains a `5TM` season.
- `docs/architecture/OFFICIAL_STATS_SCHEMA.md`, `docs/domain/BUSINESS_RULES.md`,
  `docs/architecture/IMPACT_MAP.md`, and
  `docs/validation/TEAM_SEASON_PIPELINE.md` — replace each enumeration with the
  semantic rule, and record that the check constraints enforce it in the database
  as well as in code.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_team_codes.py`
- Result: **71 passed.** New file. Covers the predicate, the `TOT` distinction,
  a 37-value corpus driven through a real SQLite check constraint to prove the
  Python and SQL forms agree, counts from 1 to 20 digits, and a 2,000-value
  random sweep over the characters that can confuse the rule.

- Command: `uv run pytest tests/unit/test_migration_snapshots.py`
- Result: **10 passed.** New file. Revision 0006 carries its check-constraint
  conditions as frozen literal text and imports nothing from `nba_data`, so an
  applied revision cannot change retroactively. These tests assert the frozen
  text still equals what `team_codes.py` generates today, and fail if the rule
  moves on without a follow-up revision.

- Command: `uv run pytest tests/unit/test_player_page_normalizer.py`
- Result: **92 passed.** Includes the Bobby Jones 2007-08 regression: the `5TM`
  season now selects **8** aggregate rows where it selected **0**.

- Command: `uv run pytest tests/unit/test_multi_team_marker_guards.py`
- Result: **68 passed.** New file. Drives a marker at every `TOT`-only guard
  and at the four check constraints.

- Command: `uv run ruff check .`
- Result: **All checks passed.**

- Command: `uv run pytest`
- Result: **689 passed, 17 skipped, 1 failed, 1 error.** The failure and the
  error are both in `tests/integration/test_api_postgres.py` and have one cause:
  `PostgreSQL schema is at ['0005_postseason_stats_tables'], not the migration
  head ['0006_synthetic_team_codes']`. The 17 skips are the new PostgreSQL
  constraint tests, which are not applicable before revision 0006 is applied and
  which CI turns into failures via `NBA_DATA_REQUIRE_POSTGRES_INTEGRATION=1`.
  Revision 0006 exists but has **not** been applied to the persistent `nba`
  database — that is a critical action and needs the owner's direct instruction.
  Every other test passes.

- Command: `uv run alembic check`
- Result: **FAILED: Target database is not up to date.** Same single cause as
  above. `uv run alembic heads` reports `0006_synthetic_team_codes (head)` and
  `uv run alembic history` shows one linear chain, so the revision graph is
  well-formed.

- Command: `uv run python scripts/validate_postgres_local.py`
- Result: **PostgreSQL validation passed.** This is the evidence that matters
  for the migration, and it runs against a uniquely named **disposable** database
  that the script creates and drops — never the persistent `nba` database. The
  script now runs `upgrade head` → `check` → `downgrade -1` → `upgrade head` →
  `check` before the tests, so revision 0006 is proven **reversible** on real
  PostgreSQL rather than only forward-applicable. All three integration files
  then pass: 1 + 2 + **17** tests, the last being the new
  `test_synthetic_team_code_constraints_postgres.py`, which drives `TOT`, `2TM`,
  `5TM`, `10TM`, `999TM` and `99999999TM` at all four constrained columns and
  confirms `BOS`, `0TM`, `1TM`, `02TM`, `TM`, `1T2M`, `T2M` and `2MT` are still
  accepted. Every insert is rolled back.

- Command: `uv run python scripts/validate_tasks.py`
- Result: **Task validation passed.**

- Read-only pre-flight against the persistent database (no writes): every value
  in `core.teams.basketball_reference_team_id` (37), `core.teams.
  current_abbreviation` (37), `core.team_aliases.abbreviation` (775), and
  `core.team_seasons.team_abbreviation` (775) was checked against the new
  predicate. **0 violating rows in all four columns**, so revision 0006 would
  apply without a constraint violation whenever the owner authorizes it.

## Manual happy path

1. Run `uv run pytest tests/unit/test_player_page_normalizer.py -k five_team -v`.
2. Confirm `test_normalize_player_page_regular_season_selects_a_five_team_aggregate_row`
   passes: 8 rows selected for season 2008, all with `source_team_code == "5TM"`.
3. Run `uv run pytest tests/unit/test_player_page_stats_loader.py -k marker -v`
   and confirm the `5TM` aggregate row loads while every `5TM` **stint** row is
   skipped with `invalid_team_stint_source_team_code`.

Expected result: the marker is accepted as a full-season aggregate source and
rejected as a team stint — the split ADR 0007 requires. The season that was
silently lost is recovered at the normalizer.

## Manual sad path

1. Run `uv run pytest tests/unit/test_multi_team_marker_guards.py -v`.
2. Confirm `get_or_create_team`, `get_or_create_team_alias`, and
   `get_or_create_team_season` each raise `ValueError` for `2TM` through `10TM`,
   and still raise for `TOT`.
3. Confirm `test_check_constraints_reject_a_marker_written_around_the_repository`
   raises `IntegrityError` for a `5TM` written by raw SQL into all four
   constrained columns.

Expected result: a multi-team marker cannot become a team, an alias, or a
team-season through the writer or around it. `TOT` behaviour is unchanged.

## Known limitations

- **The migration is written but not applied.** Revision
  `0006_synthetic_team_codes` renames the four `ck_core_*_not_tot` constraints
  to `ck_core_*_not_synthetic` and replaces their expressions. Until the owner
  authorizes `uv run alembic upgrade head`, `alembic check` and the two
  PostgreSQL integration tests fail on the version mismatch alone.
- **The rule is still expressed twice, in Python and in SQL.** A check
  constraint cannot call Python, so this is unavoidable; what is avoidable is
  drift. `multi_team_marker_sql` generates the SQL form from the same constants,
  the model constraints call it, the migration froze its output, and three
  layers of test hold the pieces together: a corpus and a random sweep through
  SQLite, a snapshot-equality test against the frozen migration text, and the
  constraints themselves exercised on real PostgreSQL. The SQL form is exact for
  a count of any length — it recognizes `<digits>TM` by deleting digits and
  checking what is left, so unlike an expression that enumerates digit positions
  it needs no arbitrary bound, and widening a constrained column cannot open a
  gap.
- **Two of the eleven listed sites cannot be reached by a marker, so their
  guards are defence in depth, not fixes.** `cache_inventory.py` takes its team
  code from a cache filename matched by `[a-z]{3}`, and
  `offline_processor._normalize_team_abbreviation` applies a three-letter shape
  check before the synthetic-code guard. Both now reject markers, and both facts
  are pinned by tests so a future change to either pattern is caught.
- **Two sites where `TOT` is a permission rather than a prohibition were
  deliberately not widened.** `loaders/team_season.py` treats `TOT` as the
  team-page aggregate row and `loaders/team_season_stats._is_aggregate_row`
  routes on it; granting markers the same permission would be wrong. Markers are
  rejected there by explicit new checks instead — `Row N uses multi-team marker`
  and the `invalid_multi_team_marker_routing` skip reason — both covered by
  tests.
- Already-persisted rows are not repaired. Bobby Jones's 2008 season stays empty
  until a backfill is authorized; that is out of scope here, as the card states.
  The recovery is now owned by a card — `tasks/planning/F4E-024`.
- **The `5TM` census in `PLAYER_PAGE_STATS_MAPPING.md` was reproduced from the
  archive audit, not re-measured.** Re-measuring means re-scanning 2,551 cached
  pages, which this card did not do. If the cache has changed since the audit,
  those figures are stale — the semantic rule they illustrate is not.
- **The `-v3` bump makes `stats.player_season_*` a three-generation table**
  (`-v1`, `-v2`, `-v3`), and F4E-022 will add a fourth. The comments beside both
  constants now document what each generation means, which is better than
  nothing and is not where someone querying the table will look. Making the
  column legible is owned by `tasks/planning/F4E-025`.
- **Three issue codes were renamed and two are new**, so any consumer reading
  validator output needs to know: `teams_tot_rows` → `teams_synthetic_code_rows`,
  `team_aliases_tot_rows` → `team_aliases_synthetic_code_rows`,
  `team_seasons_tot_rows` → `team_seasons_synthetic_code_rows`, plus the new
  `multi_team_marker_not_a_team` and `invalid_multi_team_marker_routing`.
  Nothing in this repository consumes them programmatically today.
