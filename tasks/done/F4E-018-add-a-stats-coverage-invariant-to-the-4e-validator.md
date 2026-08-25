---
id: F4E-018
title: Enforce cache-derived coverage in official-stats validation
areas:
  - data-quality
  - database-read
  - testing
  - documentation
priority: 65
depends_on:
  - F4E-016
  - F4E-017
read:
  - src/nba_data/validation/official_stats.py
  - src/nba_data/validation/offline_database.py
  - src/nba_data/cli/main.py
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
validation:
  - uv run pytest tests/unit/test_official_stats_validation.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make missing and unexpected official-stats rows fail Phase 4E validation by
comparing persisted natural keys with the independent cache-derived artifact
from F4E-017.

# Evidence and current state

`validate_offline_database` is intentionally core-only. `validate_official_stats`
reflects all 33 stats tables and checks their shape and row contents, but it has
no rule stating that a particular player-season or team stint should exist.
F4E-016 repairs report reconciliation; report totals still cannot detect one
missing key offset by one unexpected key, so coverage remains a separate and
necessary invariant.

Every issue currently makes `OfficialStatsValidationReport.passed` false. This
card follows that model: missing artifact, incompatible schema, missing keys,
unexpected keys, and unexplained source seasons are ordinary named validation
issues rather than a parallel warning system.

# Resolved validation contract

- `validate official-stats` accepts `--coverage-artifact PATH` and optional
  `--coverage-cache-root PATH` in addition to F4E-016's typed report flags.
- Omitting the artifact does not crash or skip the rest of validation. It emits
  `coverage_artifact_missing`, prints the complete report, and exits non-zero.
  A permanent invariant must not silently pass when its oracle is absent.
- Schema version 1 is required. Unknown versions emit
  `coverage_artifact_schema_unsupported` and no guessed comparison is run.
- The validator does not require cache access. Without a cache root it trusts
  the supplied artifact and reports `freshness_status: unverified` in the
  coverage summary; that status is not represented as verified and is not by
  itself a failure.
- When a cache root is supplied, the F4E-017 fingerprint is recomputed. A
  mismatch emits `coverage_artifact_stale` and prevents key comparison.
- Persisted surrogate IDs are joined through `core` to the artifact's natural
  keys before set comparison.
- Every dimension uses set equality. Expected-minus-actual is missing;
  actual-minus-expected is unexpected. Both fail independently.

# Human decisions or resources

- None.

# Acceptance criteria

- `validate_official_stats` reads a schema-version-1 F4E-017 artifact and adds a
  structured coverage summary to `OfficialStatsValidationReport`.
- Separate issue codes cover missing and unexpected keys for regular aggregate,
  postseason aggregate, regular team-stint/roster, and postseason team-stint
  dimensions. Issue context includes total count and capped natural-key examples.
- Table names are part of every expected key. The comparison detects a row in
  the wrong stats family even when the player, season, and team match.
- Aggregate keys use `(basketball_reference_player_id, season_year, table)`.
  Team-stint keys use
  `(basketball_reference_player_id, season_year, team_code, table)`.
- Did-not-play evidence suppresses only the matching aggregate expectation. It
  does not prohibit regular roster/team-stint rows derived from team pages, and
  a regular did-not-play season may legitimately have postseason rows.
- Every artifact entry under `unexplained` emits `coverage_unexplained_source`
  and fails validation.
- The artifact schema is validated before use. Invalid JSON shape and unknown
  versions produce named issues rather than `KeyError`, partial comparison, or a
  traceback.
- With `--coverage-cache-root`, a matching fingerprint is reported as verified;
  a mismatch fails before comparison. Without it, comparison still runs and the
  summary explicitly reports freshness as unverified.
- The existing Phase 4D validator remains unchanged and core-only.
- Tests cover: complete equality; one missing and one unexpected key in each
  dimension; a row in the wrong table family; a valid postseason-only season;
  did-not-play plus postseason; regular roster presence alongside a regular
  did-not-play marker; unexplained input; missing artifact; unknown schema;
  verified fingerprint; stale fingerprint; and unverified DB-only operation.
- Tests are offline and deterministic. They use local SQLite/reflection fixtures
  or existing validator fakes and never require the real cache or PostgreSQL.

# Scope

- `src/nba_data/validation/official_stats.py` and the F4E-017 artifact reader.
- `src/nba_data/cli/main.py` for the two coverage options and JSON loading.
- Focused validation tests and durable validation documentation.

# Out of scope

Building the artifact (F4E-017), changing backfill report schemas (F4E-016),
repairing rows, running a backfill, modifying Phase 4D validation, or adding a
numeric tolerance or allowlist.

# Impact

`validate official-stats` gains a required correctness input and can now fail on
row-level coverage even when aggregate counts reconcile. The command remains
read-only and performs no cache access unless the caller explicitly supplies a
cache root for freshness verification.

# Implementation notes

Build actual key sets with SQLAlchemy selects over the reflected stats tables
joined to `core.players`, `core.seasons`, `core.player_seasons`,
`core.player_team_seasons`, and `core.team_seasons`. Do not load ORM objects or
reuse write-capable repositories.

Cap examples, not counts. Preserve deterministic ordering in both issue context
and serialized summaries so repeated validation produces stable output.

# Durable knowledge updates

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — record set-equality coverage as
  a standing Phase 4E invariant.
- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — document artifact creation,
  verified and unverified invocations, and the new failure codes.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_official_stats_validation.py`
  Result: `48 passed` (31 pre-existing + 17 coverage tests, after review fixes below).
- Command: `uv run pytest tests/unit/test_stats_coverage_artifact.py`
  Result: `34 passed` — regression guard on the `compute_cache_fingerprint`
  extraction, plus the 3 tests added during review (below).
- Command: `uv run ruff check .`
  Result: `All checks passed!`
- Command: `uv run pytest`
  Result: `839 passed, 25 skipped` in ~24s (skips are pre-existing PostgreSQL
  integration tests, unrelated to this change; nothing new skipped).

## Fixed during review

A first-pass review of this branch (before this card moved to `tasks/review/`)
found one correctness bug and two test-coverage gaps against this card's own
acceptance criteria. All three are fixed and covered by new tests, above.

1. **High — malformed artifacts could bypass validation and crash.**
   `_entry_from_dict` in `stats_coverage.py` cast `regular_aggregate_tables` /
   `postseason_aggregate_tables` straight into a tuple with no per-element type
   check, and coerced team-stint `team_code`/`table` with a blind `str(...)`
   that silently accepts any type. A mixed-type list such as
   `["stats.player_season_totals", 1]` was accepted as a valid artifact and
   only failed later, as a bare `TypeError` from `sorted()` in the comparator —
   not as the named `coverage_artifact_invalid` the acceptance criteria
   require. Fixed by adding `_require_str`, `_str_tuple`, and
   `_team_stint_tuple` helpers that raise `StatsCoverageShapeError` on a
   non-string field, so `parse_stats_coverage_artifact` now rejects this shape
   before it ever reaches the comparator. Covered by
   `test_parse_stats_coverage_artifact_rejects_a_non_string_table_name` and
   `test_parse_stats_coverage_artifact_rejects_a_non_string_team_stint_field`.
2. **Medium — three explicit acceptance-criteria scenarios were untested at the
   validator level.** The card requires tests for a valid postseason-only
   season, did-not-play plus a real postseason presence, and regular
   roster/team-stint presence alongside a regular did-not-play marker — all
   as *passing* cases. Only a failing DNP variant existed. Added
   `test_validate_official_stats_coverage_passes_a_valid_postseason_only_season`,
   `test_validate_official_stats_coverage_passes_did_not_play_regular_plus_real_postseason`,
   and `test_validate_official_stats_coverage_passes_regular_roster_presence_with_did_not_play`,
   each deleting the matching DB rows via raw SQL so the artifact and the
   database agree and `report.passed is True`.
3. **Medium-low — no regression test proved fingerprint compatibility over a
   real cache.** The existing "matching fingerprint" test used an empty cache
   root, so both `build_stats_coverage_artifact` and `compute_cache_fingerprint`
   trivially hashed zero rows — a divergence between their two discovery loops
   would not have been caught. Added
   `test_compute_cache_fingerprint_matches_the_build_path_for_a_non_empty_cache`,
   which writes a real player page and team-season page to an `HtmlCache` and
   asserts the two functions produce the identical digest.

## Manual happy path

1. Built a real (non-mocked) player-page/team-season cache in a scratch
   directory from `tests/fixtures/html/team_season_coverage_bos_2000.html`,
   then ran `uv run nba-data validate build-stats-coverage --cache-root <cache>
   --output <coverage.json>` for real.
   Expected/actual: exit 0; JSON summary `entries: 1`,
   `regular_team_stint_expectations: 2`, `unexplained: 0`, `source_issues: 0`;
   the written artifact has `schema_version: 1` and one entry for
   `piercpa01`/2000 with `regular_team_stints` at `BOS` for
   `stats.player_team_season_roster` and `stats.player_team_season_totals`.
2. `uv run nba-data validate official-stats --help`
   Expected/actual: `--coverage-artifact` and `--coverage-cache-root` both
   appear with their help text, alongside the existing three report flags.
3. `CliRunner` invocation of `validate official-stats --coverage-artifact
   <path> --coverage-cache-root <path>` against a monkeypatched engine/session
   (`test_cli_validate_official_stats_passes_coverage_artifact_and_cache_root_options`).
   Expected/actual: the CLI reads the artifact JSON and forwards it, along
   with the cache-root `Path`, as keyword arguments to
   `run_official_stats_validation`; exit 0.

Expected result: all three matched.

## Manual sad path

1. `validate_official_stats(session)` with no `coverage_artifact` against the
   in-memory SQLite fixture (`test_validate_official_stats_coverage_missing_artifact_still_runs_the_rest_of_validation`).
   Expected/actual: `passed=False`, `coverage_artifact_missing` present,
   `coverage_summary == {"status": "missing"}`, and every other Phase 4E check
   still ran (`table_counts` covers all 33 tables).
2. Same session with an artifact whose `schema_version` is `2`
   (`test_validate_official_stats_coverage_rejects_unsupported_schema_version`).
   Expected/actual: `coverage_artifact_schema_unsupported`, no `dimensions` key
   in `coverage_summary` — comparison never ran.
3. Same session with `cache_fingerprint` deleted from the artifact
   (`test_validate_official_stats_coverage_rejects_a_malformed_artifact_shape`).
   Expected/actual: `coverage_artifact_invalid`, no traceback, no `dimensions`.
4. Same session with a correct-shaped artifact but a forged `cache_fingerprint`
   digest plus `--coverage-cache-root` pointing at a real (empty) directory
   (`test_validate_official_stats_coverage_detects_a_stale_fingerprint`).
   Expected/actual: `coverage_artifact_stale`, no key-comparison issue codes
   present — comparison skipped.

Expected result: all four matched.

## Known limitations

- I could not run `validate official-stats` end-to-end against a live
  PostgreSQL database in this session — Docker Desktop's daemon was not
  running here, so no local dev database was reachable, and I did not start
  one without being asked. The DB-facing behavior (freshness verification,
  the four-dimension key diff, all coverage issue codes) is exercised through
  45 focused unit tests against a real SQLAlchemy `Session` on an in-memory
  SQLite database reflecting the actual `stats.*`/`core.*` schema shape — the
  same technique the pre-existing 31 tests in this file already used — plus a
  real (non-mocked) `build-stats-coverage` CLI run. To finish the manual pass
  against Postgres yourself: start the local dev database, run
  `uv run nba-data validate build-stats-coverage --output reports/stats-coverage.json`
  against a real cache, then
  `uv run nba-data validate official-stats --coverage-artifact reports/stats-coverage.json`
  (add `--coverage-cache-root "$SCRAPER_CACHE_DIR"` to also verify freshness).
