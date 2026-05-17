# Phase 2 - Scraper Cache Integration

Status: in_progress
Phase ID: `phase-2-scraper-cache-integration`

## Goal

Integrate the current scraping flow with `BasketballReferenceClient` and
`HtmlCache` without rewriting the whole scraper.

## Allowed Work

- Adapt team-season fetch/cache seams.
- Add tests with mocks only.
- Add and use local HTML fixtures.
- Add pure parser flow for cached team-season HTML.
- Document scraper/cache integration decisions.
- Avoid real scraping in tests and validation.

## Forbidden Without Owner Approval

- Live scraping.
- Contacting Basketball Reference.
- Deleting Peewee or legacy scraper code.
- Migrating the whole database.
- API implementation.
- Frontend implementation.
- OVR, ranking, similarity, or ML feature implementation.
- Full SQLAlchemy loader migration.

## Sensitive Gates

- Any network request to Basketball Reference.
- Any command that runs the legacy scraper against the live site.
- Deleting raw data, local databases, Peewee models, or legacy modules.
- Schema migrations beyond small reviewed foundations.

## Current Task State

- `F2-001`: Adapt team-season fetch/cache flow - done.
- `F2-002`: Create pure parser flow for cached team-season HTML - done.
- `F2-003`: Add realistic HTML fixtures without live scraping in tests - done.
- `F2-004`: Adapt legacy team-season scraper entrypoint to use client/cache -
  done.
- `F2-LIVE-001`: Run one-page live smoke test for adapted team-season scraper -
  pending and gated by explicit owner approval.

## Done Criteria

- Team-season HTML can be fetched once through the central client/cache path.
- Tests prove cache-first behavior without real network requests.
- Cached HTML can feed pure parser work.
- Legacy behavior remains available unless explicitly approved for change.
- Documentation and progress history are updated.

## Default Validations

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Proceed to `phase-3-parser-normalization` after the fetch/cache path is
integrated and reviewed.
