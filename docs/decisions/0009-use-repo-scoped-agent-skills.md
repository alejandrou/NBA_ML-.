# ADR 0009 - Use Repo Scoped Agent Skills

## Status

Accepted

## Context

The project needs reusable AI instructions that travel with the repository and
do not depend on any one coding assistant.

## Decision

Store skills in `.agents/skills/<skill-name>/SKILL.md`, in tool-neutral Markdown
with `name` and `description` frontmatter only. Route them by task `areas`
through `.agents/index.md` rather than listing skills in each task card.

## Consequences

Agents use project-specific workflows without relying on chat memory. Skills stay
composable and selectively loadable, so a task pays only for the context it needs.

## Alternatives Considered

- Global-only skills: less portable.
- Chat-only instructions: easy to lose.
- One universal skill: cheap to write, expensive to load, and it drifts.
- Per-card skill lists: duplicated across cards and drifts from reality.
