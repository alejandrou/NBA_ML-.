# Phase 3 - Parser Normalization

Status: done
Phase ID: `phase-3-parser-normalization`

## Goal

Expand pure parsing and normalization for cached NBA source HTML while keeping
network, parsing, normalization, validation, and loading responsibilities
separate.

## Completed Scope

- Added an explicit supported team-season parser table mapping.
- Preserved parsing from visible tables and tables hidden inside HTML comments.
- Extracted `basketball_reference_player_id` from Basketball Reference player
  links when present.
- Added normalized team-season row output with source context, stat scope,
  stable identifier fields, and conservative scraped values.
- Added data-quality checks for context, `TOT`, missing player identifiers,
  duplicate natural keys, and required empty tables.
- Added small offline fixture tests for parser, normalizer, and validator
  behavior.

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Database writes, loaders, or Alembic migrations.
- API, frontend, generated metrics, OVR, rankings, similarity, or ML work.
- Legacy/Peewee removal.
- Postseason tables, team summary tables, and salary tables.

## Done Criteria

- Core team-season parser outputs are covered by fixture tests.
- Normalized rows use stable identifiers where available.
- Parser code performs no network or database writes.
- Documentation records supported tables and known gaps.
- Offline validation passes.

## Default Validations

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`

## Next Phase Recommendation

Proceed to `phase-4-sqlalchemy-migration` after explicit owner approval. Phase
4 remains inactive and all F4 tasks remain `pending`.
