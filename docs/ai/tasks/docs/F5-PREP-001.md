---
task_id: F5-PREP-001
title: Prepare the Codex documentation workflow and Phase 5 handoff
phase: phase-5-api
task_type: docs
status: in_progress
mode: implement
skills: [docs-maintenance, codex-review]
must_read: [AGENTS.md, docs/ai/CURRENT_TASK.md, docs/ai/TASK_CARD_TEMPLATE.md]
allowed_paths: [AGENTS.md, docs/ai, docs/architecture, docs/roadmap/TASKS.md, tasks/README.md, .gitignore, scripts/dev]
forbidden_paths: [src/nba_data, alembic, tests, scrap, models, db_manager, utils]
validation: [git diff --check, uv run ruff check ., uv run pytest]
next_task: docs/ai/tasks/api/F5-001.md
---

# Scope

Create the compact Codex task-card workflow, document the planned read-only
Phase 5 API, archive the completed Phase 4E context, and improve generated-file
hygiene. Do not implement API code, dependencies, migrations, scraping, or
database changes.

## Acceptance criteria

- `CURRENT_TASK.md` points only to this card.
- The card, task-type, onboarding, token, and API architecture documents exist.
- `feature-list.json` remains valid and is not used as startup context.
- Phase 4E historical context is archived and no longer presented as active.
- Generated exports are ignored and no local useful files are deleted.
