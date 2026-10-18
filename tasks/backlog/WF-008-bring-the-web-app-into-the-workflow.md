---
id: WF-008
title: Bring the web app into the workflow
track: shared
areas:
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
validation:
  - npm --prefix web ci
  - npm --prefix web run lint
  - npm --prefix web run typecheck
  - npm --prefix web test
  - npm --prefix web run build
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
  - uv run python scripts/validate_tasks.py --all-worktrees
critical_actions:
  - Marking the new `web` job as a required status check on `main` is a GitHub repository setting the owner changes; this card only names the job.
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

- [x] **The `web` job runs on every push and pull request, with no path
      filter, and is meant to be a required check.** A required check behind a
      `paths` filter never reports on a PR that does not touch `web/` and blocks
      its merge; the job costs a couple of minutes and also catches API changes
      that break the committed OpenAPI snapshot. The owner marks it required in
      GitHub once it has passed on `main`.
- [x] **The `web` skill is written from `F7-002`'s merged code**, not decided
      up front: the commands, the file layout, the API client and generated
      types, the display rules' home, and the test conventions it actually
      uses. Nothing in it restates `WEB_ARCHITECTURE.md`; it points there.

# Acceptance criteria

- `AGENTS.md` lists `web/` as source of truth and its generated directories as
  never-commit.
- `.agents/index.md` routes `web` to `.agents/skills/web/` and
  `docs/architecture/WEB_ARCHITECTURE.md`, plus ADRs 0006, 0008, and 0019.
- CI has a `web` job on Node 22 (`actions/setup-node` with npm cache keyed on
  `web/package-lock.json`) that runs `npm ci`, lint, typecheck, test, and build
  in `web/`, plus `scripts/export_openapi.py --check` against the committed
  snapshot, on every push and pull request.

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
