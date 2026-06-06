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

- `F4E-001`: Official wide stats schema plan (`needs_review`).

`F4E-001` is documentation-only. It finalizes the reviewed `stats` schema plan
for F4E-002 and does not implement models, migrations, repositories, loaders,
backfills, or database writes.

## Pending Phase Tasks

- `F4E-002`: Stats models and Alembic migration (`pending`).
- `F4E-003`: Idempotent stats repositories (`pending`).
- `F4E-004`: Normalized rows to wide stats loader (`pending`).
- `F4E-005`: Offline stats backfill command (`pending`).
- `F4E-006`: Official stats validation checks (`pending`).

## Guardrails

- Do not run live scraping, contact Basketball Reference, refresh cache, or
  run acquisition commands.
- Do not run stats backfill commands or write to the database as part of
  F4E-001.
- Do not add SQLAlchemy stats models or Alembic migrations until `F4E-002` is
  approved.
- Do not implement repositories, loaders, validation commands, API endpoints,
  frontend pages, generated metrics, OVR, rankings, similarity,
  recommendations, or ML work.
- Do not create a branch, commit, push, or open a PR without explicit owner
  approval.

## Next Safe Action

Review `F4E-001`. After owner approval, promote `F4E-002` to implement the
reviewed `stats` models and Alembic migration.

## References

- `docs/roadmap/PHASE_GOVERNANCE.md`
- `specs/phases/phase-4e-official-wide-stats-persistence.md`
- `specs/features/F4E-001-official-wide-stats-schema-plan.md`
- `docs/architecture/OFFICIAL_STATS_SCHEMA.md`
- `docs/migration/LEGACY_STATS_SCHEMA_REVIEW.md`
- `docs/validation/OFFLINE_DATABASE_PREPARATION.md`
- `tasks/feature-list.json`
