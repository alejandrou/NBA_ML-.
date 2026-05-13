# Workflow Protocol

All agents must follow this protocol.

## Startup

1. Read `AGENTS.md`.
2. Run `scripts/harness/init.sh`.
3. Read `docs/roadmap/CURRENT_PHASE.md`.
4. Read `tasks/feature-list.json`.
5. Read `progress/current.md`.
6. Read the relevant feature spec under `specs/features/`.

## Task Selection

- Prefer the next task with status `approved`.
- If none exists, propose the next `pending` task.
- Do not start a task if another task is `in_progress` unless explicitly instructed.

## Implementation

1. Mark the task `in_progress`.
2. Update `progress/current.md`.
3. Implement the smallest useful change.
4. Add tests.
5. Run `scripts/harness/validate.sh`.
6. Update `docs/roadmap/CHANGELOG_LEARNING.md`.
7. Move the task to `needs_review`.

## Review

1. Reviewer reads the diff.
2. Reviewer checks acceptance criteria.
3. Reviewer runs or verifies validations.
4. Reviewer updates `progress/review.md`.
5. If issues exist, mark `changes_requested`.
6. If approved, mark `done`.

## Close

1. Run `scripts/harness/close.sh`.
2. Update `progress/history.md`.
3. Clear or archive `progress/current.md`.
4. Update `docs/roadmap/TASKS.md`.
5. Summarize for the owner.
