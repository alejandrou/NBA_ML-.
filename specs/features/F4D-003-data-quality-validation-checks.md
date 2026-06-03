# F4D-003 - Data Quality Validation Checks

## Goal

Add post-load checks proving the local PostgreSQL database is coherent enough
for future read-only API development.

These checks validate the result of the offline backfill. They do not implement
API endpoints and do not trigger scraping, cache refresh, data deletion, or
destructive migrations.

## Functional Requirements

- Count loaded team seasons.
- Count loaded player seasons.
- Count player-team-season relationships.
- Detect duplicate logical rows.
- Detect orphan player/team season relationships.
- Detect teams with no players where unexpected.
- Detect seasons with suspiciously low counts.
- Check quarantine and failure counts from the backfill report.
- Produce a clear validation report with actionable failures.

## Technical Requirements

- Query the local SQLAlchemy/PostgreSQL data created by the offline backfill.
- Keep generated metrics separate from official scraped data.
- Preserve the rule that `TOT` is not a real team.
- Tests must cover passing and failing quality checks.
- Tests must not contact Basketball Reference or require live scraping.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4D-003-data-quality-validation-checks.md`.
- Validation counts loaded team seasons, player seasons, and
  player-team-season relationships.
- Validation detects duplicate logical rows.
- Validation detects orphan player/team season relationships.
- Validation detects teams with no players where unexpected.
- Validation detects seasons with suspiciously low counts.
- Validation checks quarantine and failure counts.
- Validation produces a clear report.
- Tests cover passing and failing quality checks.
- No API implementation is introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh or acquisition.
- Data deletion or destructive migrations.
- API endpoints.
- Frontend.
- Generated metrics, OVR, ranking, similarity, recommendations, or ML work.
