# Workflow Protocol

All agents must follow this protocol.

## Startup

1. Read `AGENTS.md`.
2. Run `scripts/harness/init.sh`.
3. Read `docs/roadmap/PHASE_GOVERNANCE.md`.
4. Read `docs/roadmap/CURRENT_PHASE.md`.
5. Read `tasks/feature-list.json`.
6. Read the current phase spec under `specs/phases/`.
7. Read `progress/current.md`.
8. Read the relevant feature spec under `specs/features/` when an executable
   task has one.

## Source Of Truth

- `docs/roadmap/CURRENT_PHASE.md` is the operational state of the current phase.
- `tasks/feature-list.json` is the executable task state.
- `specs/phases/*.md` is the contract and design record for phases.
- `docs/roadmap/PHASE_GOVERNANCE.md` defines status rules and fallback logic.

If these sources disagree, do not implement feature work. Report the conflict
and propose the smallest state fix.

## Codex Context Strategy

For Codex tasks, prefer reusable repository context over long prompts.

Use:

- `docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md`
- `docs/ai/CODEX_USAGE_OPTIMIZATION.md`
- `docs/ai/PHASE_<ID>_CODEX_CONTEXT.md`
- `docs/ai/PROMPT_TEMPLATES.md`

At the start of every new phase branch, create a compact phase context file
using `docs/ai/PHASE_CONTEXT_TEMPLATE.md`.

## Task Selection

Follow `docs/roadmap/PHASE_GOVERNANCE.md` for all task selection.

- If any task is `in_progress`, continue that task and do not start another.
- If the current phase is `blocked`, do not implement.
- If the current phase is `done`, create or propose a phase transition summary
  before changing phases.
- If one current-phase task is `approved`, work on that task.
- If there is no `approved` task, inspect current-phase `ready` tasks.
- If the phase is `proposed`, do not auto-promote `ready` tasks to `approved`.
- If the phase is `approved` or `in_progress`, a `ready` task may be promoted
  only when it is within allowed work and avoids sensitive gates.
- If there are no current-phase `ready` tasks, propose the next current-phase
  `pending` task.
- Never stop without proposing a next task, unblock step, or transition step.

## Implementation

1. Confirm the selected task is `approved`.
2. Confirm no other task is `in_progress`.
3. Mark the task `in_progress`.
4. Update `progress/current.md`.
5. Implement the smallest useful change.
6. Add or update tests.
7. Run `scripts/harness/validate.sh`.
8. Update `docs/roadmap/CHANGELOG_LEARNING.md`.
9. Move the task to `needs_review`.

## Review

1. Reviewer reads the diff.
2. Reviewer checks acceptance criteria.
3. Reviewer runs or verifies validations.
4. Reviewer updates `progress/review.md`.
5. If issues exist, mark `changes_requested`.
6. If approved and validation passed, mark `done`.

## Close

1. Run `scripts/harness/close.sh`.
2. Update `progress/history.md`.
3. Clear or archive `progress/current.md`.
4. Update `docs/roadmap/TASKS.md`.
5. Summarize for the owner.
