# ADR 0013 - Use Feature List JSON

## Status

Superseded by pointer-based task cards.

## Context

Tasks need machine-readable status, acceptance criteria, validation, and scope.

## Decision

Use `tasks/feature-list.json` as the structured task list.

## Consequences

The former JSON board is retired. Task cards are the editable source of truth;
a generated index may be added later only when a real consumer needs one.

## Alternatives Considered

- Markdown-only task board: readable but less structured.
