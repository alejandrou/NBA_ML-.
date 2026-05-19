# ADR 0010 - Use uv

## Status

Accepted

## Context

The repository has no stable Python dependency workflow.

## Decision

Use `uv` with `pyproject.toml`.

## Consequences

Developers run `uv sync`, `uv run pytest`, and `uv run ruff check .`.

## Alternatives Considered

- Poetry: useful but not currently integrated.
- requirements-only: simpler but weaker for tooling.
