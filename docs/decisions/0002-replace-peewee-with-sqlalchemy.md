# ADR 0002 - Replace Peewee with SQLAlchemy

## Status

Accepted

## Context

The prototype uses Peewee and direct table creation.

## Decision

Use SQLAlchemy 2.0 for all new database code and migrate Peewee progressively.

## Consequences

Legacy Peewee remains until migrated. No new Peewee code should be added.

## Alternatives Considered

- Keep Peewee permanently: lower immediate effort but weaker migration story.
- Rewrite everything now: too risky for Phase 1.
