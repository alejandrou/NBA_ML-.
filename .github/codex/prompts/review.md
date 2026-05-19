# Codex Review Prompt

Review this repository change with the `codex-review` skill.

Check:

- rate limiter respected;
- no live requests in tests or CI;
- no secrets or `.env`;
- no new Peewee code;
- SQLAlchemy/Alembic consistency;
- HTML cache usage for scraping workflows;
- parser purity;
- `TOT` is not treated as a real team;
- no `player_name` as a stable key;
- idempotency and data quality;
- docs and learning changelog updated;
- maintainability.

Return findings first, ordered by severity, with file and line references.
