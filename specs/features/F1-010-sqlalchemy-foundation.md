# F1-010 - SQLAlchemy Foundation

## Goal

Add SQLAlchemy and Alembic foundation without migrating legacy data.

## Context

The prototype uses Peewee. New schema work should use SQLAlchemy 2.0.

## Requirements

- Add DeclarativeBase.
- Add engine/session helpers.
- Add initial raw/core models.
- Add Alembic foundation.
- Document Peewee migration phases.

## Acceptance Criteria

- New DB model files import successfully.
- Alembic metadata points at SQLAlchemy models.
- Peewee remains in place as legacy.

## Validation

- `uv run pytest`
- `uv run alembic check`

## Out of Scope

- Full DB migration.
- Deleting Peewee models.

## Learning Notes

Alembic makes schema changes versioned and reviewable.
