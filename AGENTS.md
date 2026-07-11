# Repository instructions

This repository is an NBA data platform. New code belongs under `src/nba_data/`;
`scrap/`, `models/`, `db_manager/`, `utils/`, and `scrape_main.py` are legacy
read-only areas unless a task card explicitly includes them.

## Task workflow

1. Read `docs/ai/CURRENT_TASK.md`.
2. Read only the referenced task card.
3. Apply its declared `mode`, skills, `must_read`, allowed paths, and
   validation commands.
4. Use focused `rg` searches before opening additional files.
5. Update the task card status and progress requested by the card.

The task card is the source of truth for the active task. `tasks/feature-list.json`
remains machine-readable project history and is not a default Codex startup
input. Do not read long history, review, or learning logs unless the card asks.

Modes:

- `plan`: analyze and design; change only explicitly requested planning docs.
- `implement`: implement only the task-card scope; do not perform unrelated
  refactors.
- `review`: inspect the diff and validations; do not broaden scope and only fix
  small issues when the card permits it.

## Stable guardrails

- Do not run live scraping, contact Basketball Reference, or run backfills
  without explicit owner approval and the approved flags.
- Do not write to the database or apply migrations unless the task explicitly
  authorizes it.
- Do not add FastAPI/API, frontend, OVR, ranking, similarity, or ML work outside
  its approved phase.
- Keep raw scraped data, core identity, official `stats`, and generated
  `features` separate. `TOT` is never a real team and `player_name` is not a
  stable key.
- Do not mix legacy scraping code with the future API.
- Never commit, push, create branches, or open PRs unless explicitly requested.
- Run the validation commands declared by the task card; do not run live
  acquisition as validation.

See `docs/ai/CODEX_START_HERE.md` for human onboarding and
`docs/ai/TASK_TYPES.md` for skill guidance. Those files are not mandatory
startup reads.
