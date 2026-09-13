# Repository instructions

NBA data platform: Basketball Reference scraper → PostgreSQL → read-only FastAPI.

## Paths

- **Source of truth:** `src/nba_data/`, `tests/`, `alembic/`, `scripts/`, `tasks/`, `docs/`, `.agents/`, `README.md`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.github/`
- **Legacy, read-only** unless a card explicitly includes them: `scrap/`, `models/`, `db_manager/`, `utils/`, `scrape_main.py`, `etl_process.ipynb`
- **Never edit or commit:** `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `data/`, `reports/`, `logs/`, coverage output, database dumps, IDE-local files
- **Never commit:** `.local/` — the worktree's track binding, set by the user, and the claim lock managed by `scripts/claim_task.py`

## Task lifecycle

```text
tasks/planning/ → tasks/backlog/ → tasks/active/ → tasks/review/ → tasks/done/
```

**The folder is the status.** Cards carry no `status` field.

- `planning/` — work that is **not ready to start**: it still needs research, a
  user decision, resources, splitting, or has ambiguous acceptance criteria or
  unknown validation commands. Never implemented directly.
- `backlog/` — work that **is** ready to start; this is the roadmap. There is no
  roadmap document.
- `active/` — tasks being implemented.
- `review/` — tasks awaiting the user's testing.
- `done/` — history. Never loaded by default.

**Tracks.** Every card outside `done/` carries `track: data | app | shared`.
`data` owns scraping, schema, migrations, features, and ML. `app` owns the API
and web, and only reads the database. `shared` is the workflow, CI,
`pyproject.toml`/`uv.lock`, this file, and any change that breaks the other
track.

**One card per track across `active/` and `review/`; a `shared` card must be the
only one.** If the slot you need is taken, do not start — stop and say which card
holds it. `planning/` and `backlog/` hold as many cards as they need.

Each track works in its own Git worktree, bound by `.local/track` (`data` in
this folder, `app` in `../Scraping nba-reference-app`). A card enters `active/`
only through `scripts/claim_task.py`, which checks and takes the slot atomically
across worktrees. What one track changes for the other is recorded in
`tasks/CROSS_TRACK.md`. Details: `tasks/README.md` and ADR 0018.

Only the user moves a card from `review/` to `done/`.

`tasks/manifests/` is not part of the lifecycle. It holds approved live-acquisition
manifests used by scraping code and tests. Leave it alone.

Check the lifecycle after moving a card:

```bash
uv run python scripts/validate_tasks.py
uv run python scripts/validate_tasks.py --all-worktrees
```

## Short commands

| Command | Skill |
|---|---|
| `Plan this task: <description>` | `.agents/skills/plan-task/` |
| `Prepare <TASK-ID> for implementation.` | `.agents/skills/prepare-task/` |
| `Start the next task.` · `Start the next data task.` · `Start the next app task.` | `.agents/skills/start-task/` |
| `Park the current task.` · `Resume <TASK-ID>.` | `.agents/skills/park-resume/` |
| `Refill the backlog.` | `.agents/skills/backlog-planning/` |
| `Review the current task.` | `.agents/skills/review/` |
| Anything involving Git | `.agents/skills/git-control/` |

`Start the next task.` selects only from `tasks/backlog/`, and only cards of this
worktree's track or `shared`. It never reads `tasks/planning/`.

Route yourself to skills and durable documents through **`.agents/index.md`**,
using the card's `areas`. Do not load all documentation for every task.

## Git

Never run any of these without an explicit user instruction naming the operation:

```text
git add    git commit   git push    git pull   git fetch    git merge
git rebase git reset    git restore git clean  git stash    git checkout
git switch git branch -d  git branch -D  git worktree add  git worktree remove
gh pr create
```

**Exceptions** — each authorizes exactly these operations and nothing else:

- `Start the next task.` (any track form): `git fetch origin`,
  `git switch --detach origin/main`, and creating and switching to the task's
  `feature/<id>-<slug>` branch.
- `Park the current task.`: `git add` of explicit paths outside `tasks/`, one
  `WIP:` commit on the card's branch, `git fetch origin`, and
  `git switch --detach origin/main`.
- `Resume <TASK-ID>.`: `git fetch origin`, `git switch` to the card's existing
  branch, `git merge --no-edit origin/main`, and `git merge --abort` only if that
  merge conflicts.

`Plan this task` and `Prepare <TASK-ID> for implementation.` authorize no Git
operation at all.

Inspecting Git (`status`, `diff`, `log`, `branch --show-current`, `branch --list`,
`merge-base`, `worktree list`) and `gh pr list` / `gh pr view` is always fine.
Never stage with `git add .` or `-A`. Never discard or hide unrelated user
changes. Details in `.agents/skills/git-control/`.

## Critical actions — ask first, every time

Live scraping · contacting Basketball Reference or any external source · large
acquisition jobs · backfills against real or shared data · applying a migration
to a shared, persistent, or production-like database · deleting or overwriting
real datasets · destructive database operations · touching credentials or
secrets · paid external services · destructive filesystem commands · any Git
mutation not authorized above.

A card may *note* that a critical action will be needed. The card never
authorizes it — only the user's direct, current instruction does.

Everything else in a selected task is safe and needs no approval: reading,
editing source, writing tests, updating docs, creating migration files without
applying them, running offline tests, linting, disposable local fixtures, a
disposable local dev database, and moving cards between lifecycle folders.

### Live-scraping approval gate

The `--owner-approved` CLI flags, the acquisition manifest schema, the
acquisition guards, and their tests form a **runtime safety interlock** that
stops an agent from hitting Basketball Reference without a human decision. It is
application behavior. Never rename, remove, weaken, or bypass it, wherever it
lives in the codebase.

## Stable technical guardrails

- Keep raw data, core identity, official `stats`, and generated `features`
  separate.
- `TOT` is never a real team. `player_name` is not a stable key.
- Do not mix legacy scraping code with the API.
- Tests and normal validation stay offline. Never use live acquisition as
  validation unless the user explicitly authorizes it for that run.
- Scraping is cache-first and rate-limited: 10 requests/minute default, never
  above 20, at least 6 seconds apart, honor `Retry-After`, stop on 429.
- Only the `data` track writes Alembic revisions. A revision is applied to the
  persistent `nba` database only from merged `origin/main` and with the user's
  approval — never from a task branch. Reviews use a disposable database.

## Precedence

User's current instruction → this file → `.agents/index.md` and the routed skills
→ the active card → durable architecture, domain, and ADR documents. Git history
is the archive. When two sources conflict, say so rather than picking silently.
