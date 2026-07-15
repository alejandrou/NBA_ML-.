# Roadmap

## Phase status

| Phase ID | Status | Gate |
|---|---|---|
| phase-4e-official-wide-stats-persistence | done | Closed after final offline validation. |
| maintenance | done | WF-005 closed; workflow migration complete. |
| phase-5-api | active | Explicit owner approval is required before activation. |
| phase-6-frontend | planned | Starts only after Phase 5 closure. |
| phase-7-features-ovr | planned | Starts only after Phase 6 closure. |

## Phase 4E closure

Phase 4E is complete. Official stats remain separated from generated features;
live acquisition, backfills, database writes, and migrations remain owner-gated.
Its technical contracts are retained in architecture, validation, phase specs,
and ADRs rather than operational workflow documents.

## Maintenance gate

The workflow migration is complete. F5-001 is closed. Phase 5 is active;
implementation remains gated by the active task card and its declared scope.

## Future phases

Phase documents describe durable phase scope. Task cards are the executable
contracts for current and future work; historical feature specs are not startup
context.
