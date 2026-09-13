---
name: park-resume
description: Use when the user says "Park the current task." or "Resume <TASK-ID>."; sets aside a data or app task that discovered shared work, freeing its track slot, and later brings it back once the shared card is done.
---

A `data` or `app` task that needs `shared` work — a dependency or `uv.lock`
change, CI, `AGENTS.md`, `.agents/`, the workflow, or a change that breaks the
other track — **stops without any Git mutation** and reports what it found.
Nothing below runs until the user says one of the two commands, and each
authorizes exactly the Git operations it lists.

## Park the current task.

Authorizes exactly:

- `git add` of explicit paths **outside `tasks/`**, under `git-control`'s refusal
  rules
- one `git commit` with a `WIP:` subject on the card's branch
- `git fetch origin`
- `git switch --detach origin/main`

No push, stash, reset, restore, or clean.

### 1. Preconditions — read-only, all of them first

Check every one **before** writing a card, moving a file, or staging. If any
fails, stop, change nothing, and report which. There is no automatic recovery.

- This worktree's card is in `tasks/active/` or `tasks/review/`, and
  `git branch --show-current` is its `feature/<ID>-<slug>`.
- **The index is empty:** `git diff --cached --name-only` prints nothing.
  Anything already staged would ride into the WIP commit, under `tasks/` or not.
- **No commit on the branch touches `tasks/`:**
  `git log --format=%H $(git merge-base HEAD origin/main)..HEAD -- tasks/`
  prints nothing. Steps 4 and 5, and the merge in Resume, depend on it.
- **The diff touches no `shared` file** — `pyproject.toml`, `uv.lock`,
  `.github/`, `AGENTS.md`, `.agents/`, `scripts/validate_tasks.py`,
  `scripts/claim_task.py`, or anything else that is `shared` by ADR 0018. If it
  does, stop: undoing that is the user's decision.

### 2. Write the shared card

From `tasks/TEMPLATE.md`, with `track: shared`, in `tasks/planning/` — or in
`tasks/backlog/` when it already meets `prepare-task`'s readiness checklist. Any
ID family is allowed; `WF-` for workflow, CI, and tooling. In
`# Evidence and current state`, record what the parked task needs and why, with
paths, and the line:

```markdown
- Parked by: <ID> (`feature/<ID>-<slug>`)
```

`git-control` uses that line to stage the parked card's bookkeeping with this
card's closing commit.

### 3. Park the card

- Add the shared card's ID to `depends_on`.
- At the end of `# Implementation notes`, add:

  ```markdown
  ## Parked

  - Branch: feature/<ID>-<slug>
  - Waiting on: <SHARED-ID>
  - Parked: YYYY-MM-DD
  - Reason: <the shared work needed, and why>
  - Done: <what the WIP commit holds>
  - Pending: <what remains after resuming>
  ```

  `Waiting on` takes comma-separated IDs, each a `shared` card also listed in
  `depends_on`.
- Move the card to `tasks/planning/` with an ordinary filesystem move.

The validator now rejects the card anywhere but `planning/` until it records
`- Resumed:`, so neither `prepare-task` nor a manual move can promote it.

### 4. Commit the code as WIP

Stage explicit code paths outside `tasks/`, check `git diff --cached --stat`,
then commit with a `WIP:` subject. The branch carries code only; card state lives
only on the `main` line, which is why merging `main` back on resume never
conflicts under `tasks/`. With no code change at all, skip the commit.

### 5. Return to origin/main

```bash
git fetch origin
git switch --detach origin/main
```

The bookkeeping — the card in `planning/` and the new shared card — travels as
uncommitted changes under `tasks/`. If Git refuses the switch because it would
overwrite something, stop and report.

### 6. Close

Run `uv run python scripts/validate_tasks.py` and report: the slot is free; the
next step is the shared card, `Prepare <ID> for implementation.` or
`Start the next task.`, **in this folder** — its file exists only here, uncommitted
— once the other track's slot is free too.

The bookkeeping reaches `main` with the next closing commit made in this folder,
normally the shared card's own.

## Resume <TASK-ID>.

Authorizes exactly:

- `git fetch origin`
- `git switch feature/<ID>-<slug>`, the existing branch
- `git merge --no-edit origin/main`
- `git merge --abort`, **only** if that merge conflicts

Never rebase: it would need a force-push once the branch was pushed, and the
squash merge discards the merge commit anyway. Run Resume in the worktree bound
to the card's track.

### 1. Refresh and check — read-only apart from the fetch

`git fetch origin` refreshes the remote-tracking refs and Git metadata (and may
fetch tags); it does not switch HEAD or change the index or working files.
Then check, and stop without switching if any fails:

- On `origin/main` the card is in `tasks/planning/` with `## Parked` and no
  `- Resumed:` (`git show origin/main:tasks/planning/<file>`).
- Every `depends_on` ID is in `tasks/done/` on `origin/main`, and
  `# Human decisions or resources` holds no unchecked `- [ ]`.
- Exactly one branch matches: `git branch --list --ignore-case "feature/<ID>-*"`.
- The working tree has no change the switch or merge could overwrite.
- The current branch passes the **merged-branch rule** in `start-task`; being
  this card's own branch also passes, as a retry.
- The branch still has no commit touching `tasks/`:
  `git log --format=%H $(git merge-base feature/<ID>-<slug> origin/main)..feature/<ID>-<slug> -- tasks/`
  prints nothing.
- Slot pre-check, not authoritative:
  `uv run python scripts/validate_tasks.py --all-worktrees` shows this track's
  slot free and no `shared` card in progress.

### 2. Switch and merge

```bash
git switch feature/<ID>-<slug>
git merge --no-edit origin/main
```

On conflict: `git merge --abort`, stop, and report the conflicting paths.

### 3. Claim

```bash
uv run python scripts/claim_task.py --resume <ID>
```

The authoritative check. If it rejects or is busy, stop and report its message.
The state is harmless — the card's own branch with `main` merged, the card still
in `planning/` — and Resume can be retried.

### 4. Continue

1. If the merge changed `uv.lock` (`git diff --name-only ORIG_HEAD HEAD -- uv.lock`),
   run `uv sync --all-groups`.
2. Add `- Resumed: YYYY-MM-DD` to the card's `## Parked` block.
3. Run `uv run python scripts/validate_tasks.py`.
4. Continue with *Implement* and *Hand off* from `start-task`. Diffs are reviewed
   against `origin/main`, not against the WIP commit.

`planning/ → active/` here skips no readiness: the card was ready when it
started, and its only recorded blocker is the dependency step 1 verified.

A parked branch never opens a pull request by itself. It is integrated by the
normal closing of its task after Resume.
