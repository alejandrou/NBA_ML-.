# ADR 0012 - Use Agent Progress Memory

## Status

Superseded by pointer-based task cards.

## Context

The project should not depend on conversational memory.

## Decision

Use `progress/` files to record current work, history, blockers, review, and research.

## Consequences

The former `progress/` workflow is retired. Active state, blockers, review, and
handoff now live in the active task card; Git preserves historical chronology.

## Alternatives Considered

- Chat-only memory: fragile.
- Issue tracker only: useful later, but local files are immediate.
