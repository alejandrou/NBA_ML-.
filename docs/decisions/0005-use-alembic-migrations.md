# ADR 0005 - Use Alembic Migrations

## Status

Accepted

## Context

The prototype creates tables directly with ORM calls.

## Decision

Use Alembic for new schema migrations.

## Consequences

Schema evolution becomes reviewable and repeatable.

## Alternatives Considered

- ORM `create_tables()`: convenient but not enough for a data platform.
- Manual SQL only: powerful but harder to coordinate with models.
