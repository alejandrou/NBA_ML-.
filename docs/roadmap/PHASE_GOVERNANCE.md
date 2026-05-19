# Phase Governance

This document defines global phase and task governance for the rolling backlog.
It applies to every phase, not only the current one.

## Source Of Truth

- `docs/roadmap/CURRENT_PHASE.md` is the operational state of the current phase.
- `tasks/feature-list.json` is the executable state of tasks.
- `specs/phases/*.md` is the contract and design record for each phase.

If these sources conflict, stop implementation work, report the conflict, and
propose the smallest documentation or task-state fix.

## Phase Statuses

- `proposed`: The phase is designed but not approved for automatic task
  promotion.
- `approved`: The owner approved the phase, but no task is actively being
  implemented yet.
- `in_progress`: Work is actively happening in the phase.
- `review`: Implementation is complete enough for review.
- `done`: The phase is closed after validation and review.
- `blocked`: The phase cannot proceed until a blocker is resolved.

## Task Statuses

- `pending`: The task exists but is not ready for execution.
- `ready`: The task is ready to be approved within the current phase.
- `approved`: The task is selected for implementation.
- `in_progress`: The task is actively being implemented.
- `blocked`: The task cannot proceed until a blocker is resolved.
- `needs_review`: Implementation is complete and awaiting review.
- `changes_requested`: Review found changes that must be addressed.
- `done`: The task passed validation and review.
- `cancelled`: The task is intentionally closed without implementation.

## Global Rules

- Only one task may be `in_progress`.
- Multiple tasks may be `ready`.
- There may be zero or one `approved` task.
- No task may be marked `done` without validation.
- Only the current phase may have `ready` tasks.
- Future phase tasks stay `pending` until their phase becomes current.
- A `proposed` phase must not auto-promote `ready` tasks to `approved`.
- A `blocked` phase must not implement tasks.
- A `done` phase must have a phase transition summary before the current phase
  changes.

## Rolling Backlog Selection

1. Read `current_phase_id` and `current_phase_status` from
   `tasks/feature-list.json`.
2. Read `docs/roadmap/CURRENT_PHASE.md` and the current phase spec.
3. If any task is `in_progress`, continue that task and do not start another.
4. If the current phase is `blocked`, do not implement; document or propose the
   unblock step.
5. If the current phase is `done`, create or propose a phase transition summary
   before changing phase.
6. If one current-phase task is `approved`, work on that task.
7. If no task is `approved`, inspect current-phase `ready` tasks.
8. If the current phase is `proposed`, ask the owner before approving a `ready`
   task.
9. If the current phase is `approved` or `in_progress`, an agent may promote a
   `ready` task only when it is inside allowed work and avoids sensitive gates.
10. If no `ready` task exists, propose the next current-phase `pending` task.
11. Never stop with no next step. At minimum, propose the next task, unblock
    step, or transition summary.

## Sensitive Gates

Owner approval is required before any task or phase action that would:

- run live scraping;
- contact Basketball Reference or another Sports Reference site;
- exceed the conservative scraping defaults;
- delete data, raw HTML, database records, or local databases;
- remove Peewee or legacy scraper code;
- perform a full database migration;
- introduce API, frontend, OVR, ranking, similarity, or ML implementation
  outside its approved phase;
- create branches, open pull requests, or push commits;
- incur cost or require external services;
- introduce a major breaking change.

## Phase Transition Rules

- Closing a phase requires validation, progress history, and a clear statement
  of remaining risk.
- Moving to a new phase requires updating `CURRENT_PHASE.md`,
  `tasks/feature-list.json`, and the matching phase spec status.
- The first task in a new phase should be `ready`, not `approved`, unless the
  owner explicitly approves it.
