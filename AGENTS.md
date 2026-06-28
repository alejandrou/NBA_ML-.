# AGENTS.md

## Project Purpose

This repository is evolving from a Basketball Reference scraping prototype into a
maintainable NBA data platform. The long-term platform will support historical
NBA data collection, clean storage, analytics, player rankings, similarity,
a read-only API, and a future web application.

## Current Phase

Read `docs/roadmap/CURRENT_PHASE.md`.

Phase governance lives in `docs/roadmap/PHASE_GOVERNANCE.md`. The current
phase is tracked in `docs/roadmap/CURRENT_PHASE.md` and
`tasks/feature-list.json`.

## Mandatory Startup Protocol

1. Read this file.
2. Run `scripts/harness/init.sh` if available.
3. Read `docs/ai/WORKFLOW_PROTOCOL.md`.
4. Read `docs/roadmap/PHASE_GOVERNANCE.md`.
5. Read `docs/roadmap/CURRENT_PHASE.md`.
6. Read `tasks/feature-list.json`.
7. Read the current phase spec under `specs/phases/`.
8. Read `progress/current.md`.
9. Follow the rolling backlog rules for the current phase.

## Commands

Install dependencies:

```bash
uv sync
```

Run validation:

```bash
uv run ruff check .
uv run pytest
bash scripts/harness/validate.sh
```

Start local PostgreSQL:

```bash
docker compose up -d postgres
```

Legacy scraper entrypoint, only when explicitly approved:

```bash
python scrape_main.py
```

Do not run the legacy scraper during tests, CI, or Phase 1 validation.

## Mandatory Rules

- Do not run live scraping unless explicitly requested by the owner.
- Do not make HTTP requests to Basketball Reference outside the central
  rate-limited client.
- Do not exceed 10 requests/minute by default.
- Never exceed 20 requests/minute.
- Do not run live scraping in tests or CI.
- Do not hardcode secrets.
- Do not write new Peewee code.
- Do not treat `TOT` as a real team.
- Do not use `player_name` as a stable primary key.
- Keep raw scraped data separate from generated metrics.
- Prefer small, reviewable changes.
- Update docs when architecture, domain rules, schema, or workflow changes.
- Update progress files after each checkpoint.
- Ask before creating branches, opening PRs, deleting data, or running live
  scraping.

## Responsible Scraping Policy

Basketball Reference and other Sports Reference sites must be treated gently.
The project default is conservative: 10 requests/minute, a minimum delay of
6 seconds, no free concurrency, cache before network, respect `Retry-After`,
long backoff on HTTP 429, and stop after repeated 429 responses.

All future real downloads must go through `src/nba_data/scraping/client.py` and
must use `src/nba_data/scraping/cache.py` unless explicitly disabled.

## Structure

- `.agents/skills/`: repo-scoped reusable Codex skills.
- `.agents/roles/`: role instructions for leader, implementer, reviewer, and researcher.
- `docs/ai/`: rules, workflow, review protocol, and Codex notes.
- `docs/ai/REPO_MAP.md`: short repo map for targeted reads.
- `docs/ai/ARCHITECTURE_INVARIANTS.md`: stable architecture and operation rules.
- `docs/ai/tasks/`: compact AI task cards for narrow tasks.
- `docs/architecture/`: target system design.
- `docs/domain/`: NBA domain rules.
- `docs/roadmap/`: current phase, task board, decisions, and learning log.
- `tasks/feature-list.json`: structured task source of truth.
- `progress/`: current work, history, review notes, blockers, and research.
- `specs/features/`: acceptance specs for each task.
- `specs/phases/`: phase contracts and governance details.
- `src/nba_data/`: new platform foundation.
- `scrap/`, `models/`, `db_manager/`: legacy prototype code.

## Definition of Done

- Acceptance criteria met.
- Tests pass.
- Ruff passes.
- Docs updated if architecture, domain, schema, or workflow changed.
- No live scraping was run unless explicitly requested.
- Rate-limit policy respected.
- Owner learning changelog updated.
- Task status updated.
- Progress history updated.

## Prohibitions

- No API implementation before its approved phase.
- No frontend implementation before its approved phase.
- No OVR/ranking implementation before its approved phase.
- No historical scrape without explicit owner approval.
- No full Peewee removal without explicit owner approval.
- No full database migration without explicit owner approval.
- No committed `.env`, raw HTML, dumps, or local database files.

## Skills

Use `.agents/skills/<skill-name>/SKILL.md` when a task matches the skill:

- `scraping-pipeline`: scraping, parsing, cache, normalization, loading.
- `database-migration`: schema, persistence, SQLAlchemy, Alembic.
- `data-quality`: checks, fixtures, validation.
- `api-endpoint`: future FastAPI endpoints.
- `feature-engineering`: future generated metrics, OVR, rankings, similarity.
- `frontend-page`: future Next.js pages.
- `codex-review`: reviews and PR checks.

## Roles

Use `.agents/roles/leader.md`, `.agents/roles/implementer.md`,
`.agents/roles/reviewer.md`, and `.agents/roles/researcher.md` to split work.
The leader selects scope, implementer changes code, reviewer validates, and
researcher investigates without modifying production code.

## Missing Context

If context is missing, first inspect the repository. If the decision is
non-critical, use the project default, document the assumption in
`docs/roadmap/NEXT_DECISIONS.md`, and continue. Ask the owner only for actions
that can delete data, run live scraping, contact Basketball Reference, incur
cost, create branches or PRs, or introduce a major breaking change.

For narrow Codex tasks, start with `docs/ai/REPO_MAP.md` and
`docs/ai/ARCHITECTURE_INVARIANTS.md` instead of broad repository exploration.
