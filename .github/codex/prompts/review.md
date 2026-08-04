# Review prompt

Review this repository change using the `review` skill in
`.agents/skills/review/SKILL.md`, plus the domain skills routed by the task's
`areas` in `.agents/index.md`.

Check:

- rate limiter respected;
- no live requests in tests or CI;
- the live-scraping owner-approval gate is intact;
- no secrets or `.env` content;
- no `data/` or `reports/` artifacts in the diff;
- no new Peewee code;
- SQLAlchemy/Alembic consistency;
- HTML cache usage for scraping workflows;
- parser purity;
- `TOT` is not treated as a real team;
- `player_name` is not used as a stable key;
- raw / core / stats / features separation;
- idempotency and data quality;
- durable documentation updated;
- maintainability.

Return findings first, ordered by severity, with file and line references.

Do not move a task card to `tasks/done/` — only the user authorizes that.
