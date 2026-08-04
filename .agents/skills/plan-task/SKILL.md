---
name: plan-task
description: Use when the user says "Plan this task" or describes a problem, bug, or idea that is not ready to implement; researches one named idea and writes a card to tasks/planning/ without touching product code or creating a branch.
---

Command: `Plan this task: <description>`

This skill researches **one named idea**. To sweep the whole repository for what
should come next, use `backlog-planning` instead.

## Deduplicate first

Before writing anything, search for an equivalent card:

```bash
rg -l '<keyword>' tasks/planning tasks/backlog tasks/active tasks/review
rg '^id:' tasks/done
```

If one already exists, update it instead of creating a second. Say which card you
found.

## Research

1. Read `AGENTS.md` and `.agents/index.md`.
2. Read the real code and tests for the area in question. **Code and tests win
   over documents.** A document that disagrees with the code is evidence of a
   problem, not a source of truth.
3. Read `docs/architecture/IMPACT_MAP.md` when the idea crosses areas or its
   blast radius is unclear.
4. Reproduce or observe the behaviour offline where you can. Never run live
   scraping, a backfill, or a migration to investigate.

## Write the card

Create `tasks/planning/<ID>-<short-kebab-slug>.md` from `tasks/TEMPLATE.md`.

Record:

- **Evidence and current state** — what exists, what you observed, with file
  paths and line numbers. Not impressions.
- **Human decisions or resources** — every question only the user can answer, as
  `- [ ]` checkboxes. This is what keeps the card in `planning/`.
- **Impact** — components, commands, tables, documents, and tests affected.
- **Implementation notes** — the proposed split, described by name and boundary.
  **Do not mint IDs for a split you have not confirmed.** `prepare-task` mints
  them once the split survives the evidence.
- **Critical actions** — name any future live scraping, backfill, shared-database
  migration, or destructive operation in `critical_actions:`. Naming one never
  authorizes it.

`validation: []` is the planning-card convention; `prepare-task` replaces it with
real commands.

Acceptance criteria may still be rough here. If they are already sharp, every
unknown is settled, and no user decision is pending, say so — the card is ready
for `Prepare <TASK-ID> for implementation.`

## Stop

No product code. No branch. No Git mutation of any kind. Never move a card to
`tasks/backlog/` while any decision or unknown is still open.

Verify and report:

```bash
uv run python scripts/validate_tasks.py
```
