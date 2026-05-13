---
name: database-migration
description: Use when changing database models, schema, repositories, migrations, constraints, or persistence logic.
---

# Database Migration Skill

Rules:

- Use SQLAlchemy 2.0 for new DB code.
- Use Alembic for schema changes.
- Do not add new Peewee code.
- Define unique constraints for idempotency.
- Define foreign keys.
- Define indexes for common lookups.
- Use schemas: `raw`, `core`, `stats`, `features`, `ml`, `app`.
- Do not use `create_tables()` as the new schema mechanism.
- Document legacy migration from Peewee.
- Do not delete data without explicit owner approval.
