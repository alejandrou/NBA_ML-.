# Task types

Task cards declare the final authority. Typical skills are:

- `api`: `api-fastapi`, `db-readonly`, `testing`.
- `docs`: `docs-maintenance`, optionally `codex-review`.
- `data-quality`: `data-quality`, `testing`.
- `migration` or `database`: `alembic`, `db-readonly`, `testing`.
- `scraping`: the existing scraping-pipeline skill and `data-quality`.

Load only the skills named by the active card. Do not infer a larger scope from
the task type.
