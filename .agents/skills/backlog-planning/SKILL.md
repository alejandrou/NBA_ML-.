---
name: backlog-planning
description: Use when the user says "Refill the backlog" or asks what work should come next; produces a few dependency-ordered task cards without creating branches or implementing anything.
---

## Inputs

1. `AGENTS.md` and `.agents/index.md`.
2. `tasks/backlog/`, `tasks/active/`, `tasks/review/`, and the card `id`s in
   `tasks/done/`.
3. Current code and tests — what actually exists, not what documents claim.
4. Only the durable architecture and domain documents relevant to the gaps you
   find.
5. Only the most recent relevant `# Review evidence` from `tasks/done/`.

Use `rg` before opening files. Do not read all of `tasks/done/` or `specs/`.

## Produce

Roughly **three to five** cards, dependency-ordered, using `tasks/TEMPLATE.md`.

Each card must be:

- small enough for one branch and one user review cycle;
- specific enough to start without asking routine questions;
- given real acceptance criteria, not restated goals;
- given focused `validation:` commands that will actually exist;
- given `areas` that route correctly through `.agents/index.md`;
- given `depends_on` referencing real card IDs;
- given a `priority` that orders it sensibly against existing backlog cards.

List any future critical action in `critical_actions:` — naming it does not
authorize it.

## Prioritize

In order: incomplete behavior already implied by the codebase → missing
validation → gaps between architecture and implementation → user-visible
progress → coherent feature ordering → maintainability needed for the next
feature.

Do not manufacture speculative work to hit a task count. Fewer, better cards
beat a full backlog. Do not duplicate an existing backlog card.

## Stop

No branch. No implementation. No staging, commit, or push. Report the cards you
created and why, then stop.
