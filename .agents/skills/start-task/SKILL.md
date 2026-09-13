---
name: start-task
description: Use when the user says "Start the next task", "Start the next data task", or "Start the next app task", or asks which task is next; claims one eligible backlog card for this worktree's track, branches from origin/main, implements it, validates it, and moves it to review.
---

Commands: `Start the next task.` · `Start the next data task.` ·
`Start the next app task.`

This worktree's track is the content of `.local/track`. The plain command uses
it; a command naming a track must match it — otherwise stop and say which folder
holds that track.

## 1. Preflight — read-only

1. Read `AGENTS.md` and `.agents/index.md`.
2. Read `.local/track`. Missing, or neither `data` nor `app` → stop: the folder
   is not bound (`tasks/README.md`, "Working in parallel").
3. Inspect Git: `git status --short`, `git branch --show-current`.
4. **Uncommitted changes.** Card files under `tasks/` — the bookkeeping a Park
   leaves behind — travel with the new branch. Any other change → stop and
   report it. Never assume a dirty tree belongs to this task. Never clean,
   reset, restore, or stash to make room.
5. **Merged-branch rule** on the current branch, below. Fails → stop.
6. **Slot pre-check**, not authoritative:
   `uv run python scripts/validate_tasks.py --all-worktrees`. If this track's
   slot is taken, or a `shared` card is in progress in any worktree, stop and
   say which card holds it and where.
7. Mention, without acting on them: `## Open` entries in `tasks/CROSS_TRACK.md`
   whose target is a card of this track, and the card in progress in the other
   worktree.

## 2. Base

```bash
git fetch origin
git switch --detach origin/main
```

If Git refuses because the switch would overwrite local changes, stop and report.

## 3. Select

1. Read only the frontmatter of `tasks/backlog/*.md`. **Never read or select from
   `tasks/planning/`** — those cards are unprepared by definition.
2. Keep cards whose `track` is this worktree's track, or `shared`. A `shared`
   card is eligible only when no card is in progress in any worktree.
3. Exclude cards with a `depends_on` ID that is not present in `tasks/done/`.
4. Exclude cards that already have a branch
   (`git branch --list --ignore-case "feature/<ID>-*"`): they are parked or
   abandoned. Name them in the report; a parked card comes back with
   `Resume <TASK-ID>.`
5. Pick one: all dependencies done → highest `priority` → logical architectural
   order on ties → lowest ID as the final tie-breaker. Never pick a task because
   it looks easier.

If nothing is eligible for this track, stop and report exactly:

```text
No backlog tasks remain for the <track> track. Run: Refill the backlog.
```

If `tasks/planning/` holds cards of this track, add one line naming them:

```text
N card(s) wait in tasks/planning/. Run: Prepare <TASK-ID> for implementation.
```

Never invent product direction and immediately implement it. Never promote a
planning card yourself to have something to do.

## 4. Claim and branch

1. Confirm `feature/<id>-<short-kebab-slug>` does not exist.
2. Claim the slot — the authoritative check:

   ```bash
   uv run python scripts/claim_task.py <ID>
   ```

   It moves the card to `tasks/active/` only if its slot is still free across
   every worktree. Rejected or busy → stop and report its message; nothing moved,
   and HEAD sits harmlessly on `origin/main`. Never delete
   `.local/task-slot.lock` — an orphaned lock is the user's to remove.
3. Create the branch, which carries the uncommitted move because it starts from
   the same commit:

   ```bash
   git switch -c feature/<id>-<short-kebab-slug>
   ```

   If this fails after the claim, report it: the card stays visible in
   `tasks/active/`, holding the slot conservatively.

Example: `feature/F5-004-season-api-resources`. Never move a card into
`tasks/active/` by hand.

## 5. Implement

1. Load skills and durable docs per `.agents/index.md` using the card's `areas`,
   plus anything in its `read:` list.
2. Implement the acceptance criteria and nothing else.
3. **Shared work stops the task.** If it needs a dependency or `uv.lock` change,
   CI, `AGENTS.md`, `.agents/`, the workflow, or anything that breaks the other
   track, stop **without any Git mutation**, report what you found, and point to
   `Park the current task.` (`.agents/skills/park-resume/`).
4. If the card lists `critical_actions`, **ask before executing any of them** —
   the card does not authorize them.
5. **Migrations.** Only a `data` card creates Alembic revisions. Never apply a
   revision to a persistent database from a branch; validate it on a disposable
   one (`bash scripts/validate_database.sh`). The owner applies it to `nba`
   after merge.
6. Run the card's `validation:` commands, focused ones first.
7. Self-review your own diff against the acceptance criteria.

You may edit a file outside the card's stated scope when the task clearly
requires it — report the change and avoid unrelated refactoring.

## 6. Hand off

1. Fill in `# Cross-track impact`: `- None.`, or one bullet per impact on the
   other track. For each additive impact, create a handoff card in the consumer
   track's `tasks/planning/` (that track's `track:` and ID family) and add an
   entry under `## Open` in `tasks/CROSS_TRACK.md`:

   ```text
   - YYYY-MM-DD | <THIS-ID> (<track>) -> <HANDOFF-ID> (<track>) | additive | <summary>
   ```

   A breaking impact means the work is `shared`: stop and report instead.
2. Fill in `# Review evidence`: the commands you ran and their real results,
   numbered manual happy-path and sad-path steps with expected results, and any
   known limitations.
3. Move the card to `tasks/review/`.
4. **Stop.** Do not commit, do not push, do not open a PR, do not start another
   task. Report what you did and what the user should test.

Only the user moves a card from `review/` to `done/`.

## Merged-branch rule

Start and Resume check the branch currently checked out. It passes when:

- it is not a `feature/*` branch;
- `gh pr list --head <branch> --base main --state merged --json number,headRefOid`
  succeeds and lists a pull request whose `headRefOid` equals the current local
  HEAD (`git rev-parse HEAD`). A matching branch name alone is insufficient:
  commits added after the merge, or reuse of the name, must not pass. Pull
  requests are squash-merged, so ancestry alone cannot answer this;
- HEAD is detached, which is how Park always ends; or
- for Resume, it is the branch of the card being resumed.

If the GitHub check is needed and `gh` fails, returns no matching commit, or
cannot establish the result, stop and report it. Authentication or network
errors are not evidence that a branch was merged.

## Integrity check

Run it after every card move:

```bash
uv run python scripts/validate_tasks.py
```

It checks the per-track slots, tracks, areas and ID families, unique IDs,
required and forbidden frontmatter, dependency resolution, unresolved decisions
in `backlog/`, parked cards, the cross-track log, filenames, and the five
lifecycle folders. `uv run pytest` runs the same checks. Add `--all-worktrees`
to join the slots and bindings of every worktree.
