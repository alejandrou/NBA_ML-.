---
id: F4E-025
title: Centralize and validate stats parser-version lineage
areas:
  - data-quality
  - documentation
  - testing
priority: 45
depends_on:
  - F4E-022
read:
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/offline_player_postseason_stats_backfill.py
  - src/nba_data/scraping/offline_stats_backfill.py
  - src/nba_data/validation/official_stats.py
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
validation:
  - uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py tests/unit/test_offline_stats_backfill.py tests/unit/test_official_stats_validation.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make every value stored in `stats.*.parser_version` a documented parser-contract
identifier, centralize the current values, and make unknown or superseded lineage
fail official-stats validation instead of remaining an uninterpreted string.

# Evidence and current state

Every one of the 33 `stats` tables has a required `parser_version` lineage
column. Three independent backfill modules currently define their own defaults:

| Producer | Current constant before F4E-022 |
|---|---|
| Team-season pages | `team-season-parser-v1` |
| Regular player pages | `player-page-parser-v3` |
| Postseason player pages | `player-page-postseason-parser-v3` |

The player-page versions have real behavioral meaning. Version 2 fixed the
`1999-00` century rollover (F4E-013), version 3 fixed open-ended multi-team
markers (F4E-014), and F4E-022 will create version 4 by excluding did-not-play
placeholders from row selection. Existing comments describe parts of that
history, but no importable registry states which identifiers are known or
current.

`validate_official_stats` already reflects every stats table and scans lineage
for regular/postseason separation. It does not classify `parser_version`, and
because `OfficialStatsValidationReport.passed` is `not issues`, the existing
issue model already provides an unambiguous failure path for stale lineage.

The regular and postseason identifiers remain distinct. Their selectors and
destinations differ: regular player-page processing writes aggregate season
rows only, while postseason processing writes both aggregate and team-stint
rows. They have advanced together so far, but one shared identifier would
incorrectly promise that they can never diverge. What should be shared is the
registry and release generation, not the stored string.

# Human decisions or resources

- None.

# Acceptance criteria

- A single module under `src/nba_data/validation/` defines the known parser
  contracts and the current identifier for each producer: team-season,
  regular player-page, and postseason player-page.
- Each registry entry records the exact identifier, producer, generation,
  whether it is current, the task that introduced it, and a concise description
  of the behavior change. Historical player-page versions 1 through 4 and
  `team-season-parser-v1` are represented.
- The three backfill default constants are imported or derived from that
  registry rather than declared independently. Regular and postseason keep
  separate stored identifiers, and a test asserts that their current entries
  share the same generation after F4E-022.
- User-supplied `--parser-version` values remain accepted so offline experiments
  and historical reproductions are possible. The official validator, rather
  than the writer, is the enforcement boundary.
- `validate_official_stats` reports an `unknown_parser_version` issue for a value
  absent from the registry and a `stale_parser_version` issue for a known but
  non-current value. Each issue includes counts by table and version plus capped
  example grains.
- Unknown and stale versions make the validation report fail. This is deliberate:
  versions 1 through 3 are not merely old labels; they identify rows produced
  before known correctness fixes.
- The validation summary contains a dedicated parser-lineage violation counter.
- Tests cover every registered identifier, each backfill default, an unknown
  value, a stale value, mixed versions across tables, and an all-current archive.
- No row is rewritten, no migration is created, and no API field or database
  view is added.

# Scope

- A parser-contract registry under `src/nba_data/validation/`.
- The three offline stats backfill modules that currently own default constants.
- `src/nba_data/validation/official_stats.py`.
- Focused unit tests and the lineage documentation.

# Out of scope

Reprocessing or relabeling existing database rows; that remains an explicitly
authorized remediation operation. Changing parser behavior belongs to F4E-022.
Exposing lineage through the public API.

# Impact

Official-stats validation gains a new failure mode against databases that still
contain rows from superseded parser contracts. Backfill behavior is otherwise
unchanged: the same current version strings are written after F4E-022, but their
source of truth moves to one registry.

# Implementation notes

Keep the registry declarative and import-safe: it must not open a database,
inspect the cache, or import a backfill module. Backfill modules may import the
registry, never the reverse.

Group validation findings by `(table, parser_version)` rather than emitting one
issue per row. Preserve capped grain examples so the result remains actionable
without producing an enormous report.

# Durable knowledge updates

- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — replace the loose lineage
  paragraph with the registry contract and record that stale versions fail
  official-stats validation.

# Review evidence

- Command: `uv run pytest tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py tests/unit/test_offline_stats_backfill.py tests/unit/test_official_stats_validation.py tests/unit/test_parser_contracts.py`
  Result: `104 passed in 4.27s`
- Command: `uv run ruff check .`
  Result: `All checks passed!`
- Command: `uv run pytest`
  Result: `788 passed, 25 skipped, 7 warnings in 16.59s` (the 25 skips are pre-existing, unrelated integration/live-scraping tests)

A review pass caught that the initial implementation classified `parser_version`
values globally (current/stale/unknown) without checking that the identifier's
*producer* matched the table's actual producer — e.g. `team-season-parser-v1`
is current for `team_season`, so stamping it on `stats.player_season_totals`
(a `player_page_regular` table) passed validation. Fixed by adding
`StatsTableSpec.expected_parser_producer` (derived from `season_type`/`family`:
postseason tables of either family expect `player_page_postseason`, regular
aggregate tables expect `player_page_regular`, regular team-stint tables expect
`team_season`) and a new `wrong_producer_parser_version` issue code, checked
independently of staleness so a current-but-wrong-producer value is never
silently accepted. Regression tests added:
`test_validate_official_stats_rejects_a_current_version_from_the_wrong_producer`
(the exact reported scenario),
`test_validate_official_stats_rejects_a_stale_version_from_the_wrong_producer`,
and `test_parser_contracts.py::test_expected_parser_producer_matches_table_season_type_and_family`.

## Manual happy path

1. Built the throwaway SQLite fixture the validation tests already use
   (`_session_with_schema` + `_insert_clean_dataset` from
   `tests/unit/test_official_stats_validation.py`), which now stamps rows with
   the three registry-current identifiers (`team-season-parser-v1`,
   `player-page-parser-v4`, `player-page-postseason-parser-v4`).
2. Ran `validate_official_stats(session)`.
3. Ran `uv run nba-data backfill stats --help`, `backfill player-stats --help`,
   `backfill player-postseason-stats --help` (`COLUMNS=200` to avoid truncation)
   and read the printed `--parser-version` defaults.

Expected and actual result: `report.passed is True` and
`validation_summary["parser_lineage_violations"] == 0`. The three CLI defaults
printed `team-season-parser-v1`, `player-page-parser-v4`, and
`player-page-postseason-parser-v4` — unchanged from before this card, now
sourced from `current_parser_version(...)` in the registry instead of a local
constant.

## Manual sad path

1. Built the same clean fixture.
2. `update stats.player_season_totals set parser_version = 'player-page-parser-v2' where player_season_id = 1` (known but superseded).
3. `update stats.player_season_totals set parser_version = 'not-a-parser' where player_season_id = 2` (never registered).
4. Ran `validate_official_stats(session)`.

Expected and actual result: `report.passed is False`, with issues:
`stale_parser_version` for `stats.player_season_totals` /
`player-page-parser-v2` (count 1, example grain `[1]`) and
`unknown_parser_version` for `stats.player_season_totals` / `not-a-parser`
(count 1, example grain `[2]`) — one issue per `(table, parser_version)` group,
not per row, matching the existing capped-example issue shape.

5. Separately, on a fresh clean fixture:
   `update stats.player_season_totals set parser_version = 'team-season-parser-v1' where player_season_id = 1`
   (a real, currently-registered identifier — just the wrong producer's).

Expected and actual result: `report.passed is False`, `wrong_producer_parser_version`
for `stats.player_season_totals` / `team-season-parser-v1` (count 1, example
grain `[1]`), and neither `unknown_parser_version` nor `stale_parser_version`
fires for that row.

## Known limitations

- No existing database row is rewritten or relabelled; a database still
  holding pre-v4 rows will now fail `validate_official_stats` until an
  explicitly authorized remediation backfill runs. That remediation is out of
  scope for this card, as stated in its Scope section.
