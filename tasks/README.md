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
- **`active/`** — the one task being implemented. At most one file.
- **`review/`** — the one task awaiting your testing. At most one file.
- **`done/`** — completed cards, kept as lightweight history. Not loaded by
  default.

At most one card may exist across `active/` and `review/` combined. `planning/`
and `backlog/` hold as many as they need.

## Who moves what

| Move | Who |
|---|---|
| new card → `planning/` | `Plan this task: <description>`, or `Refill the backlog.` when it finds uncertainty |
| `planning/` → `backlog/` | `Prepare <TASK-ID> for implementation.`, only once nothing is pending |
| `backlog/` → `active/` → `review/` | `Start the next task.` |
| `review/` → `done/` | **only you**, by saying so explicitly |

A card may *note* that a critical action — live scraping, a backfill against real
data, a shared-database migration — will be needed. The card never authorizes it;
only your direct, current instruction does.

## Checking the lifecycle

```bash
uv run python scripts/validate_tasks.py
```

Standard library only, offline, changes nothing. `uv run pytest` runs the same
checks, so CI enforces them too.

`manifests/` is **not** part of the lifecycle. It holds approved live-acquisition
manifests consumed by the scraping code and its tests. Leave it alone.

`TEMPLATE.md` is the card format. See `AGENTS.md` for what each command
authorizes.
