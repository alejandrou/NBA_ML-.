---
id: F8-020
title: Design bounded current-season catch-up
track: data
areas:
  - planning
  - scraping
  - testing
  - documentation
priority: 88
depends_on:
  - F8-013
read:
  - docs/validation/CURRENT_SEASON_REFRESH.md
  - src/nba_data/scraping/current_season_manifest.py
  - src/nba_data/scraping/current_season_planning.py
  - src/nba_data/scraping/game_season_manifest.py
validation: []
critical_actions:
  - None during design or offline implementation. Every eventual live catch-up batch requires the owner's direct current instruction.
---

# Goal

Let F8-008 recover when more than 150 scored games have no archived box score,
without weakening the current-season refresh safety interlock.

# Evidence and current state

- F8-013 refuses the entire box-score phase above the approved ceiling. Reruns
  make no progress, and `--max-fetches` does not affect planning.
- The Stage 2 explicit-URL manifests accept only seasons 2015 through 2026;
  they cannot bootstrap season 2027 unchanged.
- F8-008 is an execution-only card and explicitly excludes changing the gate.

# Human decisions or resources

- Review recommendation: preserve the existing 150-page ceiling and refusal
  behavior. Design a separate catch-up path with explicit reviewed URLs,
  bounded batches, cache-first resume, and a report of remaining coverage.
- Resolve the new manifest kind, exact batch contract, and command surface
  before promotion. Do not reinterpret a standing refresh approval as approval
  of a catch-up batch or a live run.

# Acceptance criteria

- Specify the catch-up contract and offline validation commands before this
  card leaves planning.
- Existing refresh approval flags, ceilings, manifest checks, and refusal tests
  remain intact. Existing acquisition kinds retain their behavior.
- Offline tests cover at least 151 missing games, deterministic batch ordering,
  reruns that reduce the remaining backlog, request budgets including retries,
  missing approval, and immediate stop on 429.
- Update the runbook with an actionable bootstrap and recovery procedure.

# Scope

New current-season catch-up tooling, tests, and its runbook. No live acquisition,
database writes, changes to existing gates, or edits to approved manifests.

# Cross-track impact

- None.
