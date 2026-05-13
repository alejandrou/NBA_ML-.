# ADR 0012 - Use Agent Progress Memory

## Status

Accepted

## Context

The project should not depend on conversational memory.

## Decision

Use `progress/` files to record current work, history, blockers, review, and research.

## Consequences

Agents and the owner can resume work from versioned project files.

## Alternatives Considered

- Chat-only memory: fragile.
- Issue tracker only: useful later, but local files are immediate.
