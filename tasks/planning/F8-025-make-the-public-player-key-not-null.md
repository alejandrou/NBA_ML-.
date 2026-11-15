---
id: F8-025
title: Make the public player key NOT NULL
track: shared
areas:
  - planning
  - database-schema
  - api
  - testing
priority: 60
depends_on:
  - F8-024
read:
  - docs/validation/DATABASE_AUDIT_2026-11-10.md
  - docs/validation/MIGRATION_HEAD_HANDOVER.md
  - src/nba_data/db/models/core.py
  - src/nba_data/db/repositories/queries/players.py
  - src/nba_data/scraping/player_page_acquisition.py
  - tests/unit/test_player_api.py
  - tests/unit/test_player_query_repository.py
validation: []
critical_actions:
  - Applying the new revision to the persistent nba database — from merged origin/main, after a verified backup, with the owner's direct instruction.
---

# Goal

Finish audit H-12: `core.players.basketball_reference_player_id`, the API's
public player key, becomes `NOT NULL` in the database and in the model.

# Evidence and current state

- The column is `String(32)`, nullable (`src/nba_data/db/models/core.py:99`).
  `nba` held 0 NULLs on 2026-11-15 (read-only query during F8-024).
- The API compensates with `.is_not(None)` in `list_players` and the count query
  (`src/nba_data/db/repositories/queries/players.py:33,49`), and
  `scraping/player_page_acquisition.py:420-435` types its select as optional.
- F8-024 first made it `NOT NULL` inside revision `0013`. That broke 25 app-track
  unit tests: `tests/unit/test_player_api.py:95` and
  `tests/unit/test_player_query_repository.py:82` seed
  `Player(basketball_reference_player_id=None, ...)` to prove the filter, and
  `test_player_queries_exclude_null_ids_and_order_by_name_then_natural_key`
  exists for that case. A schema change that breaks the other track is
  `shared` work (ADR 0018), so F8-024 removed it and left `0013` data-only.

# Human decisions or resources

- [ ] Keep the API's `is_not(None)` filters as defence in depth, or remove them
      once the column cannot be NULL? Recommended: remove them and the NULL-id
      fixtures; the database guarantees it.

# Acceptance criteria

Rough:

- A new revision after `0013` makes the column `NOT NULL`; its upgrade refuses,
  changing nothing, if any row is NULL; the preflight gains the same count.
- Model typed `Mapped[str]`, `nullable=False`; mypy clean.
- App tests no longer seed a NULL-id player; the null-exclusion test is replaced
  or removed per the decision above.
- `CROSS_TRACK.md` Log entry (shared → none, breaking).

# Scope

Revision, `core.py`, `player_page_acquisition.py`, `queries/players.py` (if the
filters go), the two app test modules, preflight, handover doc.

# Out of scope

Anything else in H-11 to H-13.

# Impact

`core.players`; the players API queries and tests; the migration handover.

# Cross-track impact

- To be written when the card is prepared (shared: breaking for the app tests).

# Implementation notes

Run only when no card is in progress in either worktree.

# Durable knowledge updates

- `DATABASE_AUDIT_2026-11-10.md`: H-12 fully resolved.

# Review evidence

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
