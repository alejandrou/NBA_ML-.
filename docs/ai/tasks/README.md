# AI Task Cards

AI task cards are small, task-specific memory files for narrow work.

Use them when one spec is still too large for a short prompt and the task
benefits from a compact checklist of scope and files.

Example:

```text
docs/ai/tasks/F4E-006.md
```

## What A Task Card Can Contain

- What to read first.
- Likely files to touch.
- Files and areas that must not change.
- Validation commands.
- Expected final state.
- Commit notes.
- Scope limits and assumptions.

## Rules

- Keep cards short and factual.
- Do not duplicate full specs.
- Create a card only when a narrow task needs one.
- Treat the feature spec as the source of truth.
- Update or replace the card when the task changes materially.

## When To Use

- Long specs with repeated context.
- Tasks that will be revisited in multiple sessions.
- Review or fix-up work that needs a tighter prompt.
- Documentation-only work that should avoid re-exploring the repo.
