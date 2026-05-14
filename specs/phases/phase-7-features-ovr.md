# Phase 7 - Features And OVR

Status: proposed
Phase ID: `phase-7-features-ovr`

## Goal

Add generated metrics, player rankings, similarity, and OVR-style features only
after source data, storage, API, and frontend foundations are stable.

## Allowed Work

- Design feature tables separate from scraped stats.
- Add leakage-safe metric generation.
- Add tests for generated metrics and rankings.
- Document formulas, assumptions, and limitations.

## Forbidden Without Owner Approval

- Mixing generated metrics into raw or official stats tables.
- Training or deploying ML models with unclear data lineage.
- User-facing rankings without documented limitations.
- Live scraping as part of feature computation.

## Sensitive Gates

- Data leakage.
- Unreviewed ranking formulas.
- Reproducibility gaps.
- Expensive full-history computations.

## Initial Ready Tasks

None while this phase is proposed. Candidate tasks remain `pending` until this
phase becomes current.

## Done Criteria

- Generated metrics are stored separately from scraped data.
- Formulas and assumptions are documented.
- Tests cover representative edge cases and leakage risks.
- Validation passes.

## Default Validations

- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Create a new roadmap phase based on validated product and analytics priorities.
