# Repo Map

Use this as the first stop when a Codex task needs targeted repository memory.
Prefer `rg` before opening large files.

## Main Areas

- `docs/roadmap/`: phase state, task state, progress, changelog, and decisions.
- `docs/ai/`: reusable Codex workflow, prompt, and context docs.
- `specs/phases/`: phase contracts and scope gates.
- `specs/features/`: per-task acceptance specs.
- `tasks/feature-list.json`: executable task source of truth.
- `progress/`: current work, review notes, blockers, and history.
- `src/nba_data/`: SQLAlchemy, scraping, loader, CLI, and validation code.
- `scripts/harness/`: init, validate, close, and DB validation scripts.
- `tests/`: offline tests and fixtures.
- `scrap/`, `models/`, `db_manager/`: legacy prototype code.

## Targeted Search Rules

- Use `rg` or `rg --files` before opening large docs or source trees.
- Search for task IDs, phase IDs, model names, loader names, and command names.
- Open only the files that are directly relevant to the task.
- Stop exploratory scanning once the spec, phase context, and relevant code
  paths are identified.

## What To Read By Task Type

- Documentation only: `docs/ai/`, `docs/roadmap/`, and the exact spec.
- Phase setup or transition: `docs/roadmap/CURRENT_PHASE.md`,
  `tasks/feature-list.json`, and the phase spec.
- Implementation: exact feature spec, phase context, and the narrow source
  files it names.
- Review: the diff, the exact feature spec, `progress/review.md`, and the
  relevant validation notes.
- Scraping, loaders, or validation: `docs/ai/ARCHITECTURE_INVARIANTS.md`,
  the task spec, and the direct source files involved.
