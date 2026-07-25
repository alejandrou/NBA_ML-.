# ADR 0017 - Use A Task Folder Lifecycle

## Status

Accepted

## Context

The previous workflow spread task state across a pointer file
(`tasks/CURRENT.md`), a phase table (`docs/roadmap/ROADMAP.md`), per-card
`status`/`phase`/`mode` frontmatter, owner-approval fields, and a 216-line
Python validator under `scripts/harness/`. Every session paid to read the chain
before doing any work, the same state was recorded in several places and drifted,
and ordinary code edits required restating approval.

## Decision

The folder a card lives in **is** its status:

```text
tasks/backlog/ → tasks/active/ → tasks/review/ → tasks/done/
```

At most one card exists across `active/` and `review/` combined. `tasks/backlog/`
is the roadmap; there is no roadmap document. Cards carry no `status`, `phase`,
`mode`, `skills`, `allowed_paths`, `forbidden_paths`, or owner-approval fields.
Skills are routed by `areas` through `.agents/index.md`.

Ordinary development needs no approval. Critical actions — live scraping,
backfills against real data, shared-database migrations, destructive operations,
unauthorized Git mutations — require the user's direct current instruction, which
a task card can never supply.

## Consequences

Status cannot drift, because it has exactly one representation. A session reads
`AGENTS.md`, lists two directories, and starts working. Removing the validator
means task integrity is a short manual checklist rather than an enforced schema;
this is accepted as the cost of not maintaining a second workflow codebase.

Task history lives in `tasks/done/` and in Git.

## Alternatives Considered

- Keep the pointer and validator: enforceable, but the maintenance and per-session
  token cost exceeded the benefit for a single-agent repository.
- Status field plus flat directory: one more place for status to disagree with
  itself.
- Issue tracker outside the repo: breaks the rule that context travels with the
  codebase (ADR 0009).
