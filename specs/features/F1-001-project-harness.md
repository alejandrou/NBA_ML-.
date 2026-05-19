# F1-001 - Project Harness Documentation

## Goal

Create the core project harness documentation.

## Context

The repository should be the source of truth for agents and the owner.

## Requirements

- Add `AGENTS.md`.
- Add AI rules and skills index.
- Add architecture, domain, project spec, testing strategy, roadmap, and ADRs.

## Acceptance Criteria

- Required docs exist and describe Phase 1 scope.
- Rules prohibit live scraping, secrets, new Peewee, and unsafe rate limits.

## Validation

- `bash scripts/harness/init.sh`

## Out of Scope

- API implementation.
- Frontend implementation.
- Live scraping.

## Learning Notes

Read `AGENTS.md` first; it is the entrypoint for future work.
