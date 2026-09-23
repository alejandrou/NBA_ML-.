---
id: WF-008
title: Bring the web app into the workflow
track: shared
areas:
  - planning
  - web
  - documentation
priority: 60
depends_on:
  - F7-002
read:
  - AGENTS.md
  - .agents/index.md
  - docs/decisions/0019-scope-the-frontend-v1.md
  - docs/architecture/WEB_ARCHITECTURE.md
  - .github/workflows/ci.yml
validation: []
critical_actions: []
---

# Goal

Make `web/` a first-class part of the repository's workflow once `F7-002` has
created it: listed in `AGENTS.md`, routed by `.agents/index.md` to its durable
context and a `web` skill, and gated in CI.

# Evidence and current state

- `AGENTS.md` lists no `web/` path, and does not say never to commit
  `web/node_modules/`, `web/.next/`, or `web/.env*.local`.
- `.agents/index.md` routes the `web` area to ADRs 0006 and 0008 and says "a
  skill is pending F7-001". F7-001 decided the skill waits for real conventions,
  and that the durable context is `docs/architecture/WEB_ARCHITECTURE.md`.
- `.github/workflows/ci.yml` runs no Node job, so `web/` lint, typecheck, tests,
  and build run locally only.
- These files are `shared` (ADR 0018), so an `app` card cannot change them.

# Human decisions or resources

- [ ] Whether the web CI job is a required check on `main`, and whether it runs
      on every pull request or only when `web/` changes.
- [ ] The `web` skill's content, written from the conventions `F7-002` actually
      established.

# Acceptance criteria

Draft direction:

- `AGENTS.md` lists `web/` as source of truth and its generated directories as
  never-commit.
- `.agents/index.md` routes `web` to `.agents/skills/web/` and
  `docs/architecture/WEB_ARCHITECTURE.md`, plus ADRs 0006, 0008, and 0019.
- CI runs `npm ci`, lint, typecheck, test, and build for `web/` on Node 22.

# Scope

`AGENTS.md`, `.agents/`, `.github/workflows/`.

# Out of scope

Any change under `web/` beyond what CI needs to run.

# Impact

Both tracks' agent routing and CI.

# Cross-track impact

- None.

# Implementation notes

Keep the skill small and composable (`.agents/index.md`, "Rules").

# Durable knowledge updates

- None.

# Review evidence

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
