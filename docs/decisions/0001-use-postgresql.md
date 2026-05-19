# ADR 0001 - Use PostgreSQL

## Status

Accepted

## Context

The project needs durable relational storage for scraped NBA data and future analytics.

## Decision

Use PostgreSQL as the primary database.

## Consequences

Local development uses Docker Compose. Future production should use managed PostgreSQL.

## Alternatives Considered

- SQLite: simpler, but less suitable for schemas and analytics.
- Files only: insufficient for relationships and query workloads.
