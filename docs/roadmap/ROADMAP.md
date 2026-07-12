# Roadmap

## Phase status

| Phase ID | Status | Gate |
|---|---|---|
| phase-4e-official-wide-stats-persistence | done | Closed after final offline validation. |
| maintenance | active | Complete WF-001 through WF-005. |
| phase-5-api | planned | Explicit owner approval is required before activation. |
| phase-6-frontend | planned | Starts only after Phase 5 closure. |
| phase-7-features-ovr | planned | Starts only after Phase 6 closure. |

## Phase 4E closure

Phase 4E is complete. Official stats remain separated from generated features;
live acquisition, backfills, database writes, and migrations remain owner-gated.
Its technical contracts are retained in architecture, validation, phase specs,
and ADRs rather than operational workflow documents.

## Maintenance gate

The workflow migration is active. F5-001 is prepared but is not active until
WF-005 completes. The owner must decide whether Phase 5 remains `planned` or
becomes `active`; neither outcome authorizes API implementation automatically.

## Future phases

Phase documents describe durable phase scope. Task cards are the executable
contracts for current and future work; historical feature specs are not startup
context.
