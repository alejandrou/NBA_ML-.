# ADR 0018 - Run The Data And App Tracks In Parallel

## Status

Accepted. Supersedes the single in-progress slot of ADR 0017; the rest of ADR
0017 stands.

## Context

ADR 0017 allows one card across `tasks/active/` and `tasks/review/`, and
`Start the next task.` leaves its work uncommitted on the task branch. API and
web work cannot advance while scraping, schema, or ML work is in progress, and
the reverse.

Four facts constrain any way out:

- Alembic is a linear chain. Two lines of work that each create the next
  revision split the head.
- `/api/v1/health/ready` requires the database to be at the migration head of
  the code serving it.
- Pull requests are squash-merged, so whether a branch is merged is a question
  for `gh`, not for commit ancestry.
- Uncommitted work belongs to one checkout. Two tasks in one folder mix their
  diffs, and the Git rules forbid stashing one away.

## Decision

**Tracks.** Every card outside `tasks/done/` carries `track:`.

| Track | Owns | Areas | ID families |
|---|---|---|---|
| `data` | scraping, schema, migrations, features, ML | `scraping`, `database-schema`, `data-quality`, `ml` | F4E, F5, F8 |
| `app` | API and web; reads the database only | `api`, `web` | F6, F7 |
| `shared` | workflow, CI, `pyproject.toml` and `uv.lock`, `AGENTS.md`, and any change that breaks the other track | any | any; WF for workflow |

`database-read`, `testing`, `documentation`, `planning`, and `review` fit every
track. A `data` or `app` card in `backlog/`, `active/`, or `review/` uses only
its own and those neutral areas; `planning/` may mix them until `prepare-task`
splits the card or marks it `shared`.

**Slots.** One card per track across `active/` and `review/`. A `shared` card
needs both slots free and holds both. A missing or invalid track counts as
`shared`.

**Worktrees.** Two fixed Git worktrees, each bound to a track by an untracked
`.local/track` file: the original folder is `data`, and
`../Scraping nba-reference-app` is `app`. Start fetches `origin`, detaches onto
`origin/main`, and branches from there, so each task begins from everything the
other track has merged. It stops while the current `feature/*` branch is
unmerged.

**Atomic claim.** `scripts/claim_task.py` is the only way into `tasks/active/`.
Under one exclusive lock file, `.local/task-slot.lock` in the main worktree
created with `O_CREAT | O_EXCL`, it reads the in-progress cards of every
worktree, re-checks the candidate's binding, origin folder, dependencies, and
slot, and moves the card. The folders remain the only state; there are no
reservations to go stale. Moves out of `active/` or `review/` only free a slot
and need no lock.

**Cross-track changes.** A card in `review/` states its `# Cross-track impact`.
An additive impact gets a handoff card in the consumer track's `planning/` and
an Open entry in `tasks/CROSS_TRACK.md`, which moves to Log when the handoff card
closes. A breaking change is `shared` work.

**Park and resume.** A `data` or `app` task that discovers `shared` work stops
without touching Git. `Park the current task.` commits its code, and only its
code, as `WIP:`, moves the card to `planning/` waiting on a new `shared` card,
and detaches onto `origin/main`, freeing the slot. `Resume <TASK-ID>.` switches
back, merges `origin/main` into the branch, and claims the card again once the
`shared` card is done. Keeping card files out of branch commits is what makes
that merge free of conflicts under `tasks/`.

**Migrations.** Only `data` writes Alembic revisions, so the chain stays linear.
A revision reaches the persistent `nba` database only from merged `origin/main`,
with the owner's approval; branches and reviews use disposable databases.
Readiness is unchanged.

`scripts/validate_tasks.py` enforces tracks, areas, ID families, slots, review
impact, the cross-track log, and parked cards. `--all-worktrees` adds slots and
bindings across worktrees after the fact; it does not replace the claim's lock.

## Consequences

- Once a `data` migration is applied to `nba`, the `app` folder's older checkout
  sees a database past its head and readiness answers 503 until that folder's
  next task starts from the new `origin/main`. That is the readiness contract
  working.
- A dependency change blocks both tracks: the discovering task parks, the
  `shared` card waits for the other slot to free, and the parked task resumes
  afterwards.
- A claim killed while holding the lock leaves an orphaned lock that blocks every
  claim until the owner removes it. The claim reports the holder and never
  deletes a lock it did not create.
- Both tracks edit `tasks/CROSS_TRACK.md`, so it sees trivial line conflicts.
- Every live card needed a `track`; `tasks/done/` is exempt.

## Alternatives Considered

- **Three tracks** (scraping, schema, app): more parallel reviews than one owner
  can test, and schema work would cross a boundary on almost every card.
- **Taking turns in one folder**: one slot in practice, because unfinished work
  cannot be set aside without stashing.
- **A changelog only, without handoff cards**: the consumer track would
  rediscover changes by reading prose instead of selecting a card.
- **A copy of the database per folder**: doubles data preparation and still
  leaves which schema is canonical to convention.
- **Persistent reservations instead of claiming on the folders**: a second
  representation of status that goes stale when a session dies.
- **Rebase instead of merge on resume**: needs a force-push once the branch is
  pushed, and the squash merge discards the merge commit anyway.
