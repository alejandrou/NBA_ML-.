# Codex Phase Execution Protocol

## Purpose

This document is the reusable execution protocol for Codex tasks. Future
prompts should reference this file instead of repeating the full workflow
instructions.

## Standard Execution Flow

1. Read `AGENTS.md` and `docs/ai/CURRENT_TASK.md`.
2. Read the referenced card, declared skills, and `must_read` files only.
3. Use focused searches for any additional context.
4. Implement only the card scope and run its validations.
5. Update status/progress as the card requires.
6. Commit and push only if explicitly requested.

## Phase Context Rule

At the beginning of each new phase branch, create a phase context file:

`docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md`

Future task prompts for that phase must reference it instead of repeating long
context. Example: `docs/ai/PHASE_4E_CODEX_CONTEXT.md`.

## Fallback If Phase Context Does Not Exist

If `docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md` does not exist,
create it before implementation using:

- `docs/roadmap/CURRENT_PHASE.md`
- `tasks/feature-list.json`
- `docs/roadmap/TASKS.md`
- `progress/current.md`
- `progress/review.md`
- `specs/phases/<current-phase>.md`
- `specs/features/<current-task>.md`
- relevant `docs/architecture/*.md`
- relevant `docs/validation/*.md` if applicable

Keep it short and factual.
Do not invent status.
Do not duplicate full specs.
Do not copy long historical context.

## Context Rules

- Keep the context budget small. Read the global protocol, current phase
  context, and exact spec before opening anything else.
- Do not open the whole repository unless necessary.
- Use `rg`, `git grep`, or targeted searches before opening large files.
- Read additional files only if needed.
- Do not print full file contents unless necessary.
- Prefer repository docs as memory instead of long prompts.
- Do not repeat phase history if it already exists in progress or roadmap
  docs.
- Keep phase context compact.
- Use `docs/ai/tasks/README.md` for narrow task-specific cards instead of
  expanding the prompt.

## Scope Rules

- Do not start the next phase unless explicitly requested.
- Do not mark tasks as done unless instructed or owner-approved.
- Do not create models, migrations, repositories, loaders, backfills, API,
  frontend, or generated features outside the task scope.
- Do not run scraping live unless the task explicitly allows it.
- Do not refresh cache unless the task explicitly allows it.
- Do not perform destructive database operations unless explicitly requested.
- Do not add temporary files, database dumps, local reports, raw data,
  `.env`, or cache artifacts to git.
- Do not refactor unrelated code while making the requested change.
- Use a minimal diff that matches the spec and nothing more.
- Do not run dangerous commands unless the owner explicitly requests them.
- Do not paste full logs in the final response if the checks passed.
- Keep the final response short.

## Validation Rules

Base validation commands:

```bash
python -m json.tool tasks/feature-list.json
uv run ruff check .
uv run pytest
```

If the task changes database or migration files:

```bash
uv run alembic upgrade head
uv run alembic check
```

On Windows:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/harness/validate.sh
```

Only run heavier or DB-writing commands when the task explicitly requires
them.

## Commit And Push Rules

- Commit and push only when explicitly requested.
- Prefer one commit per phase task unless otherwise requested.
- Use a clear commit message with the task scope.
- Do not create a branch, PR, or push unless requested.
- Run `git status` before committing.
- Do not add temporary, local, or generated data files.

## Final Response Rule

Final responses should be short:

- task state
- files changed
- validation results
- commit hash if a commit was made
- next task
