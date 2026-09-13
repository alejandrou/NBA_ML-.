# Tasks

The folder a card sits in **is** its status. Cards carry no `status` field.

```text
planning/ → backlog/ → active/ → review/ → done/
```

- **`planning/`** — work that is **not ready to start**. A card belongs here while
  it still needs research, confirmation of what the code or data actually does, a
  decision from you, resources you must supply, splitting into smaller tasks, or
  while its acceptance criteria are ambiguous or its validation commands unknown.
  Nothing here is implemented directly.
- **`backlog/`** — work that **is** ready to start: concrete goal, verifiable
  acceptance criteria, defined scope, identified dependencies, real validation
  commands, and no decision left pending. This is the living roadmap; there is no
  separate roadmap document.
- **`active/`** — tasks being implemented.
- **`review/`** — tasks awaiting your testing.
- **`done/`** — completed cards, kept as lightweight history. Not loaded by
  default.

## Tracks

Two lines of work run in parallel (ADR 0018). Every card outside `done/` names
its `track:`.

| Track | Owns | Areas | ID families |
|---|---|---|---|
| `data` | scraping, schema, migrations, features, ML | `scraping`, `database-schema`, `data-quality`, `ml` | F4E, F5, F8 |
| `app` | API and web; only reads the database | `api`, `web` | F6, F7 |
| `shared` | workflow, CI, `pyproject.toml` and `uv.lock`, `AGENTS.md`, and any change that breaks the other track | any | any; WF for workflow |

`database-read`, `testing`, `documentation`, `planning`, and `review` fit every
track. Once a `data` or `app` card leaves `planning/`, it uses only its own
track's areas and these neutral ones; a mixed card is split or marked `shared`
by `prepare-task`.

## Slots

**One card per track across `active/` and `review/`.** A `shared` card needs both
slots free and holds both; a missing or invalid track counts as `shared`.
`planning/` and `backlog/` hold as many cards as they need.

Cards enter `active/` only through the claim, which checks the slots of every
worktree and moves the card in one exclusive step:

```bash
uv run python scripts/claim_task.py <TASK-ID>            # backlog/ -> active/
uv run python scripts/claim_task.py --resume <TASK-ID>   # a parked card, planning/ -> active/
```

It exits 0 when it moved the card, 1 when it rejected the claim, and 3 when the
lock stayed busy; in the last two cases nothing moved. The lock is
`.local/task-slot.lock` in the main worktree. The claim never deletes a lock it
did not create: if a killed claim left one behind, check the holder it reports
and delete the file yourself.

## Who moves what

| Move | Who |
|---|---|
| new card → `planning/` | `Plan this task: <description>`, or `Refill the backlog.` when it finds uncertainty |
| `planning/` → `backlog/` | `Prepare <TASK-ID> for implementation.`, only once nothing is pending |
| `backlog/` → `active/` → `review/` | `Start the next task.` (or `Start the next data task.` / `Start the next app task.`) |
| `active/` or `review/` → `planning/`, parked | `Park the current task.` |
| parked `planning/` → `active/` | `Resume <TASK-ID>.` |
| `review/` → `done/` | **only you**, by saying so explicitly |

A card may *note* that a critical action — live scraping, a backfill against real
data, a shared-database migration — will be needed. The card never authorizes it;
only your direct, current instruction does.

## Cross-track handoffs

Before a card moves to `review/`, its `# Cross-track impact` reads `- None.` or
lists what it changes for the other track. An additive change — a new column,
table, or endpoint the other track can adopt when it chooses — creates a handoff
card in the consumer track's `planning/` and an entry under `## Open` in
[`CROSS_TRACK.md`](CROSS_TRACK.md). Closing the handoff card moves the entry to
`## Log`. A breaking change is `shared` work.

Only the `data` track writes Alembic revisions. A revision is applied to the
persistent `nba` database only from merged `origin/main`, with your approval.

## Working in parallel

Each track has its own Git worktree, bound by an untracked `.local/track` file:

| Folder | `.local/track` |
|---|---|
| `Scraping nba-reference` (this one) | `data` |
| `../Scraping nba-reference-app` | `app` |

Set up once, after this workflow is merged:

```bash
git worktree add --detach "../Scraping nba-reference-app" origin/main
mkdir -p .local "../Scraping nba-reference-app/.local"
printf 'data\n' > .local/track
printf 'app\n' > "../Scraping nba-reference-app/.local/track"
# copy .env and COMANDOS.md into the app folder yourself
# then, inside the app folder:
uv sync --all-groups
```

`Start the next task.` in a folder picks only that folder's track, or a `shared`
card when nothing is in progress anywhere. It fetches `origin` and branches from
`origin/main`, and it stops while the folder's previous `feature/*` branch is
unmerged.

## Parking a task

A `data` or `app` task that discovers `shared` work — a dependency bump, a CI
change, a change that would break the other track — stops without touching Git
and tells you. You choose:

1. `Park the current task.` — commits the task's code as `WIP:` on its branch,
   writes a `shared` card, moves the parked card to `planning/` with a
   `## Parked` block waiting on it, and returns the folder to `origin/main`.
   The slot is free.
2. Run the `shared` card from the same folder once the other track is idle, and
   close it as usual; its closing commit carries the parked card's bookkeeping.
3. `Resume <TASK-ID>.` — switches back to the parked branch, merges
   `origin/main`, claims the card again, and continues.

The procedure and exactly which Git operations each command authorizes are in
`.agents/skills/park-resume/`.

## Checking the lifecycle

```bash
uv run python scripts/validate_tasks.py
uv run python scripts/validate_tasks.py --all-worktrees
```

Standard library only, offline, changes nothing. `uv run pytest` runs the same
checks, so CI enforces them too. `--all-worktrees` also joins the slots and
bindings of every worktree; it finds after the fact what a manual move skipped,
but it does not replace the claim.

`manifests/` is **not** part of the lifecycle. It holds approved live-acquisition
manifests consumed by the scraping code and its tests. Leave it alone.

`TEMPLATE.md` is the card format. See `AGENTS.md` for what each command
authorizes.
