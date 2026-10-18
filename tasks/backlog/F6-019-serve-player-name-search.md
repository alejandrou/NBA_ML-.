---
id: F6-019
title: Serve player name search
track: app
areas:
  - api
  - database-read
  - testing
  - documentation
priority: 50
depends_on:
  - F6-012
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - docs/decisions/0019-scope-the-frontend-v1.md
  - src/nba_data/api/routers/players.py
  - src/nba_data/api/services/players.py
  - src/nba_data/db/repositories/queries/players.py
  - tests/unit/test_player_api.py
  - tests/integration/test_api_postgres.py
validation:
  - uv run pytest tests/unit/test_player_api.py tests/unit/test_player_service.py tests/unit/test_player_query_repository.py tests/unit/test_player_name_folding.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. No schema change, extension, or write.
---

# Goal

Let a client find a player by name — `GET /api/v1/players?q=doncic` returns
Luka Dončić — case- and accent-insensitively, without any schema change, and
retire the "No name search" v1 non-promise.

# Evidence and current state

- `API_CONTRACT.md` names "No name search or filter on `/players`" as a v1
  non-promise; ADR 0019 ships the players index without search and points here.
- `core.players.full_name` is the only published name; names carry diacritics
  (`Dončić`, `Jokić`, `Porziņģis`) a user types without them. The table holds
  a few thousand rows, so a sequential scan per request is cheap; no index is
  needed.
- The database is PostgreSQL 16 with UTF-8 encoding (`docker-compose.yml`,
  image `postgres:16`). PostgreSQL ≥ 13 has `normalize(text, NFD)`, and its
  regular expressions accept `\uXXXX` ranges, so combining marks can be removed
  in SQL with no `unaccent` extension and no `data` track migration.
- Unit query tests run on SQLite (`tests/unit/test_player_query_repository.py`),
  which has no `normalize`; the folding is proven on PostgreSQL in
  `tests/integration/test_api_postgres.py`, run by `validate_database.sh`.

# Human decisions or resources

- [x] **Worth it now** (decided 2026-10-18): paging an alphabetical list of
      every player is the players index's main usability gap, and the solution
      needs no schema change. F4E-021 only documents `full_name`; it changes no
      value, so search does not wait for it.
- [x] **Parameter**: optional `q` on `GET /api/v1/players`, combined with
      `page` / `page_size`; `total` counts matches. Trimmed length 2–50, else
      422. No separate route.
- [x] **Semantics**: case- and accent-insensitive **substring** match on
      `full_name`. Both sides are folded the same way: lowercase, NFD, combining
      marks U+0300–U+036F removed. `%`, `_`, and `\` in `q` are escaped, so
      they match literally. Letters that do not decompose (`đ`, `ł`, `ø`) are
      matched as written — a documented limitation.
- [x] **Ordering unchanged**: `full_name ASC, basketball_reference_player_id
      ASC`. No relevance score: it would be a computed ranking, and the
      alphabetical order is already deterministic.
- [x] **No database index or extension.** Revisit only if `/players?q=` latency
      is measured above 100 ms; that would be a `data` handoff.

# Acceptance criteria

- `src/nba_data/domain/name_folding.py` (or the query module): one Python fold
  for `q`, and the SQL expression built next to it, both documented as the same
  rule. `tests/unit/test_player_name_folding.py` pins the Python side
  (`"Dončić"` → `"doncic"`, `"PORZIŅĢIS"` → `"porzingis"`, `"đ"` unchanged).
- `test_player_api.py`: `q` absent → unchanged behavior; `q` of length 1 or 51
  → 422; whitespace-only → 422; `q` with `%` or `_` matches literally; no match
  → 200 with an empty page and `total` 0.
- `tests/integration/test_api_postgres.py`: seeded `Luka Dončić` and
  `Nikola Jokić` are found by `doncic`, `DONČIĆ`, `jok`, and `ić`; ordering and
  `total` are correct across two pages.
- `API_CONTRACT.md`: the search contract under Players; the non-promise is
  removed. `WEB_ARCHITECTURE.md` and ADR 0019's consequence line point to the
  served search (the web search box itself is a later `F7` card).

# Scope

`src/nba_data/api/` players route, service, and query; the folding module;
tests; `API_CONTRACT.md`, `WEB_ARCHITECTURE.md`, ADR 0019's consequences.

# Out of scope

A web search box, fuzzy or phonetic matching, aliases, search on any other
resource, and any schema change.

# Impact

- One optional query parameter on an existing route.

# Cross-track impact

- None.

# Implementation notes

- Never key anything on a name; results are still players keyed by
  `basketball_reference_player_id`.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md`, `WEB_ARCHITECTURE.md`, ADR 0019.

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
