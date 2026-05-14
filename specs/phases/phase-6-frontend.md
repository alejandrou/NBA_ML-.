# Phase 6 - Frontend

Status: proposed
Phase ID: `phase-6-frontend`

## Goal

Build a future web application over the read-only API once API contracts are
stable.

## Allowed Work

- Design and implement frontend pages against stable API contracts.
- Add UI tests or smoke checks appropriate to the chosen stack.
- Document frontend workflows and data dependencies.

## Forbidden Without Owner Approval

- Bypassing the API to scrape or query raw databases directly.
- Live scraping from frontend workflows.
- OVR, ranking, similarity, or ML feature implementation.
- Production deployment.

## Sensitive Gates

- New external services.
- User-facing contract changes.
- Secrets, auth, or deployment configuration.

## Initial Ready Tasks

None while this phase is proposed. Candidate tasks remain `pending` until this
phase becomes current.

## Done Criteria

- Core frontend views work against stable read-only API data.
- UI behavior is tested or manually validated.
- No frontend workflow triggers scraping.
- Documentation records local run and validation commands.

## Default Validations

- `uv run ruff check .`
- `uv run pytest`
- Frontend validation commands once a frontend stack exists.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Proceed to `phase-7-features-ovr` after users can inspect core data through the
web application.
