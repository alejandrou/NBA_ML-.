# NBA Data Platform

A Basketball Reference scraping prototype evolving into a maintainable NBA data
platform: rate-limited scraper → raw HTML cache → parsers → normalizers →
validators → idempotent loaders → PostgreSQL → read-only FastAPI.

New code lives under `src/nba_data/`. The legacy prototype (`scrape_main.py`,
`scrap/`, `models/`, `db_manager/`, `utils/`) is read-only.

## Setup

Install `uv`, then:

```bash
uv sync
cp .env.example .env          # when you need local overrides
docker compose up -d postgres # local database
```

## Validation

```bash
uv run ruff check .
uv run pytest
git diff --check
```

Database validation — starts PostgreSQL, applies migrations, runs the
integration test. Local development only:

```bash
bash scripts/validate_database.sh
```

On Windows this needs Git Bash. `scripts/dev/start-dev.ps1` is the PowerShell
preflight equivalent for lint and tests.

## Task lifecycle

The folder a task card sits in **is** its status:

```text
tasks/backlog/ → tasks/active/ → tasks/review/ → tasks/done/
```

`tasks/backlog/` is the roadmap — there is no separate roadmap document. At most
one card exists across `active/` and `review/` at a time. `tasks/TEMPLATE.md` is
the card format, and `tasks/README.md` explains the folders.

## Working with an AI agent

`AGENTS.md` is the entry point; `.agents/index.md` routes each task's `areas` to
the skills and documents it actually needs. Short commands:

| Command | What happens |
|---|---|
| `Start the next task.` | Picks the next eligible backlog card, creates its branch, implements it, validates it, moves it to `review/`, and stops. |
| `Refill the backlog.` | Writes three to five dependency-ordered cards. No branch, no code. |
| `Review the current task.` | Reviews the diff against acceptance criteria and prepares manual test steps. |
| `Move the review task to done, commit it and push it.` | Closes the card and performs exactly those Git operations. |

You do not need to say that work is approved, which task is current, or which
files to read.

### Git restrictions

The agent never stages, commits, pushes, pulls, merges, rebases, resets,
restores, cleans, stashes, or opens pull requests unless you ask for that
specific operation. The single exception: `Start the next task.` may create and
switch to the task's `feature/<id>-<slug>` branch.

Live scraping, backfills against real data, shared-database migrations, and
other destructive or external actions always require your explicit go-ahead. A
task card can note that one is needed but never authorizes it.

## Legacy scraper

```bash
python scrape_main.py
```

Do not run this casually. It can contact Basketball Reference and write to the
legacy database.

## Responsible scraping

- 10 requests/minute against Basketball Reference
- never exceed 20 requests/minute
- minimum 6 seconds between requests
- cache before network
- no live scraping in tests or CI
- respect `Retry-After`
- stop or back off on HTTP 429

## Key docs

- `AGENTS.md` — agent entry point and repository guardrails
- `.agents/index.md` — skill and document router
- `docs/architecture/SYSTEM_DESIGN.md` — target architecture and loader invariants
- `docs/architecture/API_ARCHITECTURE.md`, `API_CONTRACT.md` — API layering and public contract
- `docs/domain/BUSINESS_RULES.md` — NBA domain rules
- `docs/specs/PROJECT_SPEC.md` — technical contract and validation rules
- `docs/decisions/` — architectural decision records
- `docs/validation/` — operational validation procedures
