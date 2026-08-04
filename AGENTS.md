# Repository instructions

NBA data platform: Basketball Reference scraper → PostgreSQL → read-only FastAPI.

## Paths

- **Source of truth:** `src/nba_data/`, `tests/`, `alembic/`, `scripts/`, `tasks/`, `docs/`, `.agents/`, `README.md`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.github/`
- **Legacy, read-only** unless a card explicitly includes them: `scrap/`, `models/`, `db_manager/`, `utils/`, `scrape_main.py`, `etl_process.ipynb`
- **Never edit or commit:** `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `data/`, `reports/`, `logs/`, coverage output, database dumps, IDE-local files

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
- `active/` — the one task being implemented. At most one file.
- `review/` — the one task awaiting the user's testing. At most one file.
- `done/` — history. Never loaded by default.

**At most one card may exist across `active/` and `review/` combined.** If either
holds a card, do not start another task — stop and say which one. `planning/` and
`backlog/` hold as many cards as they need.

Only the user moves a card from `review/` to `done/`.

`tasks/manifests/` is not part of the lifecycle. It holds approved live-acquisition
manifests used by scraping code and tests. Leave it alone.

Check the lifecycle after moving a card:

```bash
uv run python scripts/validate_tasks.py
```

## Short commands

| Command | Skill |
|---|---|
| `Plan this task: <description>` | `.agents/skills/plan-task/` |
| `Prepare <TASK-ID> for implementation.` | `.agents/skills/prepare-task/` |
| `Start the next task.` | `.agents/skills/start-task/` |
| `Refill the backlog.` | `.agents/skills/backlog-planning/` |
| `Review the current task.` | `.agents/skills/review/` |
| Anything involving Git | `.agents/skills/git-control/` |

`Start the next task.` selects only from `tasks/backlog/`. It never reads
`tasks/planning/`.

Route yourself to skills and durable documents through **`.agents/index.md`**,
using the card's `areas`. Do not load all documentation for every task.

## Git

Never run any of these without an explicit user instruction naming the operation:

```text
git add    git commit   git push    git pull   git fetch    git merge
git rebase git reset    git restore git clean  git stash    git checkout
git switch git branch -d  git branch -D  gh pr create
```

**One exception:** `Start the next task.` authorizes creating and switching to
that task's `feature/<id>-<slug>` branch — nothing else. `Plan this task` and
`Prepare <TASK-ID> for implementation.` authorize no Git operation at all.

Inspecting Git (`status`, `diff`, `log`, `branch --show-current`) is always fine.
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

## Precedence

User's current instruction → this file → `.agents/index.md` and the routed skills
→ the active card → durable architecture, domain, and ADR documents. Git history
is the archive. When two sources conflict, say so rather than picking silently.
