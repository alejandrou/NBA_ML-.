# Phase 3 - Parser Normalization

Status: proposed
Phase ID: `phase-3-parser-normalization`

## Goal

Expand pure parsing and normalization for cached NBA source HTML while keeping
network, parsing, normalization, and loading responsibilities separate.

## Allowed Work

- Add parsers that receive HTML strings and return structured data.
- Add normalization for parsed Basketball Reference rows.
- Add fixture-based tests.
- Document parser assumptions and domain rules.

## Forbidden Without Owner Approval

- Live scraping.
- Database loading beyond local test doubles.
- Full database migration.
- API implementation.
- Frontend implementation.
- OVR, ranking, similarity, or ML feature implementation.

## Sensitive Gates

- Contacting Basketball Reference.
- Treating `TOT` as a real team.
- Using player names as stable primary keys.
- Mixing generated metrics with scraped stats.

## Initial Ready Tasks

None while this phase is proposed. Candidate tasks remain `pending` until this
phase becomes current.

## Done Criteria

- Core team-season parser outputs are covered by fixture tests.
- Normalized rows use stable identifiers where available.
- Parser code performs no network or database writes.
- Documentation records supported tables and known gaps.

## Default Validations

- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Proceed to `phase-4-sqlalchemy-migration` after parser outputs are stable enough
to load idempotently.
