# Repository instructions

This repository is an NBA data platform. New code belongs under `src/nba_data/`;
`scrap/`, `models/`, `db_manager/`, `utils/`, and `scrape_main.py` are legacy
read-only areas unless a task card explicitly includes them.

## Startup and authority

1. Read this file, then `tasks/CURRENT.md`.
2. Open only the card named by its `task` field.
3. Apply the card's mode, skills, `must_read`, allowed paths, forbidden paths,
   approval gate, and validation commands.
4. Use `rg` before opening additional files; do not load directories or history
   by default.

The task card owns its operational state, scope, review, blockers, and handoff.
`tasks/CURRENT.md` is only the active-task pointer. `docs/roadmap/ROADMAP.md`
owns phase state and transition gates. Architecture, domain, validation, and ADR
documents own durable technical decisions. Git owns history.

## Work modes

- `plan`: analyze and change only card-authorized planning documents.
- `implement`: make the smallest change inside `allowed_paths`, validate it,
  and move the card to `review`.
- `review`: inspect the diff and acceptance criteria without broad refactors;
  record findings and set `done`, `blocked`, or `in_progress`.

## Scope and approval

- Do not touch `forbidden_paths` or broaden a card's scope.
- A task with `requires_owner_approval: true` cannot enter `in_progress` until
  `owner_approved: true` records approval for its declared scope.
- Do not run live scraping, contact Basketball Reference, acquire or overwrite
  cache, run backfills, write data, apply migrations, delete data, remove legacy
  code, change phases, create branches, commit, push, or open a PR without
  explicit owner approval and any required task flags.
- Do not add API, frontend, OVR, ranking, similarity, or ML work outside its
  active approved phase.

## Stable technical guardrails

- Keep raw data, core identity, official `stats`, and generated `features`
  separate. `TOT` is never a real team and `player_name` is not a stable key.
- Do not mix legacy scraping code with the future API.
- Tests and normal validation remain offline; never use live acquisition as
  validation unless a card explicitly authorizes it.

## Completion

Run the card's focused and declared validation. Update its concise `Review and
handoff` section, then change only `tasks/CURRENT.md` when selecting the next
task. Do not commit or push unless explicitly requested.
