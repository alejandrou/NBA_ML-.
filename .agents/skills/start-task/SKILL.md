---
name: start-task
description: Use when the user says "Start the next task" or asks which task is next; selects one eligible backlog card, creates its branch, implements it, validates it, and moves it to review.
---

## Select

1. Read `AGENTS.md` and `.agents/index.md`.
2. Inspect Git read-only: `git status --short`, `git branch --show-current`.
3. If `tasks/active/` or `tasks/review/` holds a card, **stop** and report which
   one. Never start a second task.
4. Read only the frontmatter of `tasks/backlog/*.md`. **Never read or select from
   `tasks/planning/`** — those cards are unprepared by definition.
5. Exclude cards with a `depends_on` ID that is not present in `tasks/done/`.
6. Pick one: all dependencies done → highest `priority` → logical architectural
   order on ties → lowest ID as the final tie-breaker. Never pick a task because
   it looks easier.

If the backlog is empty, stop and report exactly:

```text
No backlog tasks remain. Run: Refill the backlog.
```

If `tasks/planning/` is not empty, add one line naming those cards:

```text
N card(s) wait in tasks/planning/. Run: Prepare <TASK-ID> for implementation.
```

Never invent product direction and immediately implement it. Never promote a
planning card yourself to have something to do.

## Branch

Before creating anything, confirm the working tree is clean and the branch does
not already exist. Stop if unrelated user edits could be overwritten. Never
clean, reset, restore, or stash to make room. Never assume a dirty tree belongs
to this task.

```bash
git switch -c feature/<id>-<short-kebab-slug>
```

Example: `feature/F5-004-season-api-resources`.

This is the **only** Git mutation `Start the next task.` authorizes.

## Implement

1. Move the card file to `tasks/active/`.
2. Load skills and durable docs per `.agents/index.md` using the card's `areas`,
   plus anything in its `read:` list.
3. Implement the acceptance criteria and nothing else.
4. If the card lists `critical_actions`, **ask before executing any of them** —
   the card does not authorize them.
5. Run the card's `validation:` commands, focused ones first.
6. Self-review your own diff against the acceptance criteria.

You may edit a file outside the card's stated scope when the task clearly
requires it — report the change and avoid unrelated refactoring.

## Hand off

1. Fill in the card's `# Review evidence`: the commands you ran and their real
   results, numbered manual happy-path and sad-path steps with expected results,
   and any known limitations.
2. Move the card to `tasks/review/`.
3. **Stop.** Do not commit, do not push, do not open a PR, do not start another
   task. Report what you did and what the user should test.

Only the user moves a card from `review/` to `done/`.

## Integrity check

Run it after every card move:

```bash
uv run python scripts/validate_tasks.py
```

It checks concurrency across `active/` and `review/`, unique IDs, required and
forbidden frontmatter, dependency resolution, unresolved decisions in `backlog/`,
filenames, and the five lifecycle folders. `uv run pytest` runs the same checks.
