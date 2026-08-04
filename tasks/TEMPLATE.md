---
id: XX-000
title: Concise imperative title
areas:
  - api
priority: 50
depends_on: []
read: []
validation:
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

What this task delivers and why.

# Evidence and current state

What exists today, what behaviour was observed, and the evidence that proves the
problem or the need. Cite files and commands, not impressions.

# Human decisions or resources

- None.

In `tasks/planning/` this may hold open questions as `- [ ]` checkboxes. In
`tasks/backlog/` it must read `- None.` or contain only resolved `- [x]` items —
a card with an unresolved decision is not ready to start.

# Acceptance criteria

- Specific, checkable statements.

# Scope

Files, layers, or behaviours this task may change.

# Out of scope

What it deliberately does not touch.

# Impact

Components, commands, tables, schemas, documents, interfaces, and tests this
change affects.

# Implementation notes

Constraints, patterns to follow, references, known risks.

# Durable knowledge updates

Permanent documents to update if the implementation confirms new knowledge.
`- None.` when the change teaches nothing durable.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
