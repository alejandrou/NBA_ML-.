# ADR 0009 - Use Repo Scoped Codex Skills

## Status

Accepted

## Context

The project needs reusable AI instructions that travel with the repository.

## Decision

Store skills in `.agents/skills/<skill-name>/SKILL.md`.

## Consequences

Agents can use project-specific workflows without relying on chat memory.

## Alternatives Considered

- Global-only skills: less portable.
- Chat-only instructions: easy to lose.
