---
name: prepare-task
description: Use when the user says "Prepare <TASK-ID> for implementation"; resolves a planning card's open questions from code and tests, splits it if oversized or mixed across tracks, and promotes it to tasks/backlog/ only when it is genuinely ready to start.
---

Command: `Prepare <TASK-ID> for implementation.`

Turns one card in `tasks/planning/` into a card that can be started without
asking routine questions. Promotion is the whole point — refusing to promote a
blocked card is a success, not a failure.

## Load

1. `AGENTS.md` and `.agents/index.md`.
2. The card in `tasks/planning/`.
3. The skills and durable documents its `areas` route to, plus its `read:` list.

**A parked card is not preparable.** If `# Implementation notes` holds
`## Parked` without `- Resumed:`, stop: it comes back only through
`Resume <TASK-ID>.` (`.agents/skills/park-resume/`). Never promote it.

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
concerns, has acceptance criteria that cannot all be verified together, or
**mixes areas of the `data` and `app` tracks**. A mixed card becomes one card per
track wired by `depends_on`; when the pieces cannot ship separately — or the
change would break the other track — mark it `track: shared` instead.

Mint the new IDs here, each in its track's family (F4E, F5, or F8 for `data`; F6
or F7 for `app`; WF or any family for `shared`), and wire `depends_on` in
dependency order. Each piece must independently satisfy the readiness checklist
below. Pieces that are still uncertain stay in `planning/`.

## Complete the card

A card is ready for `tasks/backlog/` only when all of this holds:

- the goal is concrete;
- acceptance criteria are specific and verifiable, not restated goals;
- scope and out-of-scope are explicit;
- `track:` is set, and a `data` or `app` card's ID family matches it;
- `depends_on` names real card IDs;
- `read:` lists the documents an implementer actually needs;
- `areas:` routes correctly through `.agents/index.md`, covers everything the
  task will change, and fits the track — a `data` or `app` card uses only its
  track's areas plus the neutral ones;
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
