# ADR 0014 - Use Harness Scripts

## Status

Accepted

## Context

Agents and humans need repeatable startup, validation, and close checks.

## Decision

Use `scripts/harness/init.sh`, `validate.sh`, and `close.sh`.

## Consequences

Validation becomes easier to run before review.

## Alternatives Considered

- Manual command lists: easy to skip.
