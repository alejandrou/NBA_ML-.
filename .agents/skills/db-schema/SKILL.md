---
name: db-schema
description: Use for explicitly approved SQLAlchemy schema, model, constraint, index, or Alembic migration work; do not use for read-only queries, loaders, or API tasks.
---

## Use when

The active card changes database schema, SQLAlchemy models, constraints,
indexes, or Alembic revisions and explicitly authorizes that work.

## Boundaries

Use SQLAlchemy 2.0 and Alembic for new schema changes. Keep cached raw source
material, core, stats, features, ML, and app data separate. Define reversible
upgrade and downgrade paths, appropriate foreign keys, unique constraints for
idempotency, and indexes for supported lookup patterns. Do not introduce new
Peewee code.

## Approval and validation

Inspect current revisions first. Never apply a migration, write data, or delete
data unless the active card records the required owner approval. Test upgrade
and downgrade where the card requires it, run the declared checks, and keep
read-only application access in `db-readonly` query repositories.
