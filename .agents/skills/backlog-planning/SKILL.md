---
name: backlog-planning
description: Use when the user says "Refill the backlog" or asks what work should come next; sweeps the repository for real gaps and writes a few dependency-ordered cards, without creating branches or implementing anything.
---

This skill **sweeps the whole repository** for what should come next. To research
one already-named idea, use `plan-task` instead.

## Inputs

1. `AGENTS.md` and `.agents/index.md`.
2. `tasks/planning/`, `tasks/backlog/`, `tasks/active/`, `tasks/review/`, and the
   card `id`s in `tasks/done/`.
3. Current code and tests — what actually exists, not what documents claim.
4. Only the durable architecture and domain documents relevant to the gaps you
   find. `docs/architecture/IMPACT_MAP.md` when a gap crosses areas.
5. Only the most recent relevant `# Review evidence` from `tasks/done/`.

Use `rg` before opening files. Do not read all of `tasks/done/`.

## Produce

Roughly **three to five** cards where real gaps exist, dependency-ordered, using
`tasks/TEMPLATE.md`.

Route each card by how ready it is:

- **`tasks/backlog/`** — only when it fully meets the bar below, and its
  `# Human decisions or resources` reads `- None.`
- **`tasks/planning/`** — when significant uncertainty remains: the current
  behaviour is unconfirmed, a user decision is pending, the scope needs splitting,
  or the validation commands are unknown.

A suspicion is never an implementation card. When you notice something looks
wrong but cannot yet prove what or why, that is a `planning/` card describing the
evidence — not a `backlog/` card describing a fix.

Each `backlog/` card must be:

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
beat a full backlog. Do not duplicate a card that already exists in `planning/`,
`backlog/`, `active/`, `review/`, or `done/`.

## Stop

No branch. No implementation. No staging, commit, or push. Report the cards you
created, which folder each went to and why, then stop.

```bash
uv run python scripts/validate_tasks.py
```
