---
id: F6-019
title: Design player name search
track: app
areas:
  - planning
  - api
  - database-read
priority: 50
depends_on:
  - F6-012
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - docs/decisions/0019-scope-the-frontend-v1.md
  - src/nba_data/db/models/core.py
validation: []
critical_actions: []
---

# Goal

Decide whether and how the API offers player name search, so the frontend can
find a player without paging an alphabetical list of every player.

# Evidence and current state

- `API_CONTRACT.md` names "No name search or filter on `/players`" as a
  deliberate v1 non-promise: "`player_name` is not a stable key, and search is
  its own design problem."
- ADR 0019 ships the players index without search and names this card as the
  gap's owner.
- `core.players.full_name` is the only published name. Names carry diacritics
  in the source (`Dončić`), which a user will type without them.

# Human decisions or resources

- [ ] Match semantics: prefix, substring, or token match; case- and
      accent-insensitive or not.
- [ ] The query parameter (`q` on `/players`, or a separate route) and its
      ordering — alphabetical, or relevance.
- [ ] Whether it needs a database index or extension (`unaccent`, `pg_trgm`).
      Either is a `data` track migration and a cross-track handoff.
- [ ] Whether search is worth it at all before the database change the owner
      plans.

# Acceptance criteria

Draft direction:

- `API_CONTRACT.md` records the search contract, or records why v1 stays
  without it.
- Any schema need is handed to the `data` track as a planning card with a
  `tasks/CROSS_TRACK.md` entry.

# Scope

Contract design only.

# Out of scope

Implementation, migrations, and the frontend search box.

# Impact

`API_CONTRACT.md`; possibly a `data` handoff card.

# Cross-track impact

- None.

# Implementation notes

Search must return players keyed by `basketball_reference_player_id`; a name is
never a key.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md`.

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
