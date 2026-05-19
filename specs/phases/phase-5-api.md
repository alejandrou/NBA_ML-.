# Phase 5 - API

Status: proposed
Phase ID: `phase-5-api`

## Goal

Add a read-only API over reviewed NBA data after the storage layer is stable.

## Allowed Work

- Design read-only API endpoints.
- Add request/response schemas.
- Add service-layer queries over SQLAlchemy data.
- Add tests for API behavior without live scraping.
- Document API contracts.

## Forbidden Without Owner Approval

- Mutating API endpoints.
- Live scraping from API requests.
- Frontend implementation.
- OVR, ranking, similarity, or ML feature implementation.
- Production deployment.

## Sensitive Gates

- Public API contract changes.
- Auth, secrets, or deployment changes.
- Expensive queries over large historical datasets.

## Initial Ready Tasks

None while this phase is proposed. Candidate tasks remain `pending` until this
phase becomes current.

## Done Criteria

- Read-only API endpoints have tests and documented contracts.
- API does not trigger scraping.
- Query behavior is bounded and predictable.
- Validation passes.

## Default Validations

- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Proceed to `phase-6-frontend` after the read-only API is stable.
