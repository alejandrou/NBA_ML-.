---
name: prepare-task
description: Use when the user says "Prepare <TASK-ID> for implementation"; resolves a planning card's open questions from code and tests, splits it if oversized, and promotes it to tasks/backlog/ only when it is genuinely ready to start.
---

Command: `Prepare <TASK-ID> for implementation.`

Turns one card in `tasks/planning/` into a card that can be started without
asking routine questions. Promotion is the whole point — refusing to promote a
blocked card is a success, not a failure.

## Load

1. `AGENTS.md` and `.agents/index.md`.
2. The card in `tasks/planning/`.
3. The skills and durable documents its `areas` route to, plus its `read:` list.

## Resolve

Settle every unknown that code, tests, or documents can answer. Read the actual
implementation — do not carry a claim from a document into acceptance criteria
without checking it. Replace each resolved `- [ ]` with `- [x]` and the answer,
or delete it and fold the answer into the card body.

## Escalate

If a question genuinely needs the user — a product decision, a credential, a
sample file, an external resource, a trade-off only they can make — **leave the
card in `tasks/planning/`**, list exactly what you need, and stop. Do not invent
an answer to unblock yourself.

## Split

Split when the card exceeds one branch and one review cycle, mixes unrelated
concerns, or has acceptance criteria that cannot all be verified together.

Mint the new IDs here, in the same numbering family, and wire `depends_on` in
dependency order. Each piece must independently satisfy the readiness checklist
below. Pieces that are still uncertain stay in `planning/`.

## Complete the card

A card is ready for `tasks/backlog/` only when all of this holds:

- the goal is concrete;
- acceptance criteria are specific and verifiable, not restated goals;
- scope and out-of-scope are explicit;
- `depends_on` names real card IDs;
- `read:` lists the documents an implementer actually needs;
- `areas:` routes correctly through `.agents/index.md`, and covers everything the
  task will change;
- `validation:` lists **real commands that exist**, focused ones before global
  ones;
- `critical_actions:` names any future live scraping, backfill, shared-database
  migration, or destructive operation — naming one never authorizes it;
- `# Human decisions or resources` reads `- None.` or holds only resolved `- [x]`
  items.

Drop `planning` from `areas:` when the card moves.

## Move and verify

Move the file from `tasks/planning/` to `tasks/backlog/` with an ordinary
filesystem move — not `git mv`, which stages the change. Then:

```bash
uv run python scripts/validate_tasks.py
```

## Stop

No product code. No branch. No commit, push, or PR. Report which cards you
promoted, which stayed in `planning/`, and exactly what each blocked card needs.
