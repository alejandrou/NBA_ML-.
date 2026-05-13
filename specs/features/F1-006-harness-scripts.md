# F1-006 - Harness Scripts

## Goal

Add repeatable startup, validation, and close scripts.

## Context

Agents and humans need one obvious way to check project health.

## Requirements

- Add `scripts/harness/init.sh`.
- Add `scripts/harness/validate.sh`.
- Add `scripts/harness/close.sh`.
- Scripts must not contact the network or run scraping.

## Acceptance Criteria

- Init checks required files.
- Validate runs Ruff and Pytest when available.
- Close checks validation and staged unsafe files.

## Validation

- `bash scripts/harness/init.sh`
- `bash scripts/harness/validate.sh`

## Out of Scope

- Live environment checks.

## Learning Notes

Scripts make "done" reproducible.
