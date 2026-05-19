# F1-003 - Feature List and Specs

## Goal

Create machine-readable tasks and human-readable specs.

## Context

Phase work needs acceptance criteria and validation commands.

## Requirements

- Add `tasks/feature-list.json`.
- Add feature specs for Phase 1 tasks.

## Acceptance Criteria

- Every Phase 1 task has id, title, status, acceptance criteria, validation,
  expected files, and out-of-scope items.
- Every Phase 1 task has a spec file.

## Validation

- `bash scripts/harness/init.sh`

## Out of Scope

- Issue tracker automation.

## Learning Notes

Use tasks for state, specs for implementation intent.
