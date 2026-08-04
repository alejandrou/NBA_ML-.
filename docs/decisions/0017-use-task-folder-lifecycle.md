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
tasks/planning/ → tasks/backlog/ → tasks/active/ → tasks/review/ → tasks/done/
```

`tasks/planning/` holds work that is not ready to start — it still needs
research, a user decision, resources, splitting, or has ambiguous acceptance
criteria. `tasks/backlog/` holds work that is ready. `Start the next task.`
selects only from `backlog/` and never reads `planning/`, so an unprepared card
cannot be picked up by accident. `plan-task` writes into `planning/`;
`prepare-task` is the only path from `planning/` to `backlog/`.

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
`AGENTS.md`, lists two directories, and starts working.

The 216-line `scripts/harness/` validator was removed. A stdlib-only
`scripts/validate_tasks.py` replaces it: no YAML dependency, unit-tested, one
command, and enforced through `uv run pytest` rather than a second CI pipeline.
Five folders plus a readiness gate are more state than a manual checklist holds
reliably, but the checker stays small enough to read in one sitting — it is a
script, not a workflow codebase.

Splitting `planning` from `backlog` costs one extra transition per task. In
exchange, "ready to start" becomes a property the selector can see rather than
prose it must interpret, and unresolved questions stop being discovered
mid-implementation.

Task history lives in `tasks/done/` and in Git.

## Alternatives Considered

- Keep the pointer and the old harness: enforceable, but the maintenance and
  per-session token cost exceeded the benefit for a single-agent repository.
- Status field plus flat directory: one more place for status to disagree with
  itself.
- A single `backlog/` with a "not ready" convention in prose: relies on text the
  selector cannot act on, so `Start the next task.` would eventually pick an
  unprepared card.
- Issue tracker outside the repo: breaks the rule that context travels with the
  codebase (ADR 0009).
