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
