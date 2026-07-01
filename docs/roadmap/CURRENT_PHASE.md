# Current Phase

Phase ID: `phase-4e-official-wide-stats-persistence`
Status: `in_progress`

## Phase 4E - Official Basketball Reference Wide Stats Persistence

## Goal

Add persistence for official Basketball Reference player statistics in typed
wide relational tables under schema `stats`, while keeping identity and
relationships in `core` and future generated metrics in `features`.

Phase 4E remains pre-API. Phase 5 API work must not begin until Phase 4E is
complete unless the owner explicitly approves a core-only API path.

## Phase 4D Closure Baseline

Phase 4D is closed as `core relational database readiness`. The owner confirmed
these PostgreSQL counts after the full offline backfill:

```text
core.seasons                26
core.teams                  37
core.team_aliases           775
core.team_seasons           775
core.players                2551
core.player_seasons         12676
core.player_team_seasons    14344
```

The saved backfill report at `reports/offline-backfill-2000-2025.json`
contains 775 selected inventory entries, 775 loaded entries, 129000 loaded
rows, 0 failed entries, and 0 quarantined entries.

The Phase 4D closure source is `docs/validation/OFFLINE_DATABASE_PREPARATION.md`,
plus the final closure notes in `progress/review.md`. The requested
`docs/validation/PHASE_4D_CORE_DATABASE_CLOSURE.md` file is not present.

## Active Checkpoint

- `F4E-001`: Official wide stats schema plan (`done`) by explicit owner
  approval of the reviewed contract in
  `docs/architecture/OFFICIAL_STATS_SCHEMA.md`.
- `F4E-002`: Stats models and Alembic migration (`done`) by explicit owner
  approval of the reviewed SQLAlchemy models, Alembic migration, and tests.
- `F4E-003`: Idempotent stats repositories (`done`) by explicit owner
  approval of the reviewed repositories, tests, and validation.
- `F4E-004`: Normalized rows to wide stats loader (`done`) by explicit owner
  approval of the reviewed loader, tests, and validation.
- `F4E-005`: Offline stats backfill command (`done`) by explicit owner
  approval of the reviewed guarded command, tests, and validation.
- `F4E-006`: Official stats validation checks (`changes_requested`) because
  validator/design guidance still contains outdated `TOT` and numeric-range
  assumptions.
- `F4E-007`: Player-page regular-season aggregate stats backfill (`ready`).
- `F4E-008`: Postseason stats schema and player-page backfill (`pending`).
- `F4E-009`: Official stats final validation and database closure (`pending`).

`F4E-002` implements the reviewed schema as SQLAlchemy models and Alembic
revision `0003_stats_wide_tables`. `F4E-003` adds idempotent SQLAlchemy
repositories over those stats tables without owning transaction commits,
creating core rows, loading normalized rows, or introducing backfill behavior.
`F4E-004` adds the normalized-row loader over those repositories without
owning transaction commits, creating core rows, or running offline stats
backfills. `F4E-005` adds the guarded cache-only stats backfill command and is
closed by explicit owner approval. `F4E-006` added read-only validation over
the initial official `stats` tables, but review now requests updates for
synthetic source-code handling and Basketball Reference numeric ranges before
Phase 4E can close. `F4E-007` is the next safe implementation task.

## Guardrails

- Do not run live scraping, contact Basketball Reference, refresh cache, or
  run acquisition commands.
- Do not run the real stats backfill command or write real stats backfill data
  as part of review preparation.
- Do not implement API endpoints, frontend pages, generated metrics, OVR,
  rankings, similarity, recommendations, or ML work.
- Do not create a branch, commit, push, or open a PR without explicit owner
  approval.

## Next Safe Action

Start `F4E-007` only after normal approval/promotion. Keep Phase 5 pending
until Phase 4E closes through `F4E-009`.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4e-official-wide-stats-persistence.md`
- `specs/features/F4E-001-official-wide-stats-schema-plan.md`
- `specs/features/F4E-002-stats-models-and-alembic-migration.md`
- `specs/features/F4E-003-idempotent-stats-repositories.md`
- `specs/features/F4E-004-normalized-rows-to-wide-stats-loader.md`
- `specs/features/F4E-005-offline-stats-backfill-command.md`
- `specs/features/F4E-006-official-stats-validation-checks.md`
- `specs/features/F4E-007-player-page-regular-season-aggregate-stats-backfill.md`
- `specs/features/F4E-008-postseason-stats-schema-and-player-page-backfill.md`
- `specs/features/F4E-009-official-stats-final-validation-and-db-closure.md`
- `docs/architecture/OFFICIAL_STATS_SCHEMA.md`
- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`
- `docs/migration/LEGACY_STATS_SCHEMA_REVIEW.md`
- `docs/validation/OFFLINE_DATABASE_PREPARATION.md`
- `tasks/feature-list.json`
