# F1-002 - Agent Roles and Progress

## Goal

Add reusable role instructions and progress memory.

## Context

Agents need clear responsibilities and external memory.

## Requirements

- Add `.agents/roles`.
- Add `.agents/skills`.
- Add `progress/current.md`, `history.md`, `review.md`, `blockers.md`, and `research/`.
- Add workflow and review protocols.

## Acceptance Criteria

- Roles and skills exist.
- Progress files are initialized.
- Workflow and review protocols are documented.

## Validation

- `bash scripts/harness/init.sh`

## Out of Scope

- External orchestration.

## Learning Notes

Progress files are a lightweight local memory system.
