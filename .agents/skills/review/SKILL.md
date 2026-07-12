---
name: review
description: Use when reviewing a repository diff, task completion, or pull request without broad implementation work.
---

## Workflow

Read the active card, inspect the diff, compare it with scope and acceptance
criteria, and verify declared validation. Report findings by severity with file
and rationale. Check scope creep, offline-test boundaries, secrets, data and
domain invariants, and task-card handoff.

## Boundaries

Do not perform broad refactors or implement substantial new work during review.
Use the relevant domain skill alongside this one for API, data, scraping, or
schema-specific checks. Set the card to `done`, `blocked`, or `in_progress`
according to the evidence.
