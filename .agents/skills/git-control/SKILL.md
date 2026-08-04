---
name: git-control
description: Use for any Git operation in this repository — inspecting state, grouping changes, staging, writing commit messages, committing, or pushing; defines what is authorized without an explicit user instruction.
---

## Authorization

Inspection is always allowed: `git status`, `git diff`, `git log`,
`git branch --show-current`, `git show`.

**Mutations require an explicit user instruction naming the operation:**

```text
git add    git commit   git push    git pull   git fetch    git merge
git rebase git reset    git restore git clean  git stash    git checkout
git switch git branch -d  git branch -D  gh pr create
```

**One exception:** `Start the next task.` authorizes creating and switching to
that task's `feature/<id>-<slug>` branch. It authorizes nothing else — not
staging, not committing, not pushing.

`Plan this task: <description>` and `Prepare <TASK-ID> for implementation.`
authorize **no** Git operation at all, not even a branch. They move card files
between lifecycle folders with ordinary filesystem moves; use a plain move rather
than `git mv`, which stages the change.

A pull request always needs its own explicit instruction. Never `--no-verify`,
never bypass signing.

## Inspect before any commit

```bash
git status --short
git branch --show-current
git diff --stat
git diff
```

If anything is staged, also:

```bash
git diff --cached --stat
git diff --cached
```

Never assume all modified files belong in one commit.

## Refuse to stage

- `.env` or any secret material
- anything under `data/` (including `data/raw/` HTML caches) or `reports/`
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`
- coverage output, logs, database dumps, IDE-local files

Respect the real `.gitignore`. If one of these appears staged, stop and say so.

Never use `git add .` or `git add -A`. Stage explicit paths after reviewing the
change set. Never discard or hide unrelated user changes.

## Group by purpose

bug fix · feature · documentation · test · refactor · build or dependency ·
performance · style · work in progress

When unrelated changes are mixed, recommend separate commits rather than one
combined commit.

## Commit messages

Prefixes: `BUG:` `ENH:` `DOC:` `TEST:` `REF:` `COMP:` `PERF:` `STYLE:` `WIP:`

Subjects: imperative mood, capitalized after the prefix, no trailing period,
under 72 characters and ideally near 50, explaining intent rather than
implementation detail.

Bodies: what changed, why, how at a useful level, alternatives considered,
limitations, validation performed, and manual testing where useful.

## Commit workflow

1. Inspect the complete Git state.
2. Summarize the changed files.
3. Detect unrelated changes.
4. Recommend commit grouping.
5. Prepare explicit staging.
6. Propose commit messages.
7. Execute **only** the operations the user asked for.
8. Report the resulting commit and push state.

When the user asks to commit and push in one instruction, do not add an extra
approval prompt after inspecting the change set — unless the set is ambiguous or
contains unrelated work.

## Closing a task

`Move the review task to done, commit it and push it.` authorizes: inspecting
the change set, moving the card from `tasks/review/` to `tasks/done/`, staging
explicit paths, committing, and pushing the branch. It does not authorize opening
a pull request.

This is the only instruction that moves a card into `tasks/done/`. Run
`uv run python scripts/validate_tasks.py` after the move and before staging.
