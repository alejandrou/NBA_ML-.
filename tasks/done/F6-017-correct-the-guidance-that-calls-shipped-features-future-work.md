---
id: F6-017
title: Correct the guidance that calls shipped features future work
areas:
  - documentation
  - api
priority: 36
depends_on: []
read:
  - .agents/skills/api-fastapi/SKILL.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/API_CONTRACT.md
  - .github/workflows/ci.yml
  - docs/validation/TESTING_STRATEGY.md
  - docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md
  - tasks/done/F6-005-implement-api-database-readiness-endpoint.md
  - tasks/done/F6-002-api-postgresql-integration-coverage.md
validation:
  - uv run ruff check .
  - uv run pytest
  - uv run python scripts/validate_tasks.py
  - git diff --check
critical_actions: []
---

# Goal

Make two sentences of routing guidance describe what the repository actually
contains. Both call a shipped, tested feature "future" work, and both sit in
documents an agent reads *before* touching the API — so they are exactly the
sentences most likely to cause a working feature to be re-planned or removed on
suspicion.

Finding 5 of [the 2026-09-08 project and database audit](../../docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md).

# Evidence and current state

Two stale claims, one in each document:

- `.agents/skills/api-fastapi/SKILL.md:33` ends with "Readiness is a separate
  future task." Readiness shipped in F6-005: the route, its three fixed `detail`
  strings, and the per-request rule are fixed in
  `docs/architecture/API_CONTRACT.md:50-74`; the service is
  `src/nba_data/api/services/readiness.py`; `tests/unit/test_api_readiness.py`
  and `tests/integration/test_api_unreachable_database.py` cover it. The audit's
  OpenAPI inspection listed readiness among the six versioned paths.
- `docs/architecture/API_ARCHITECTURE.md:58` ends with "real DB integration is a
  future, separate layer." That contradicts the same file twelve lines earlier —
  lines 32-46 specify the readiness probe's runtime boundaries in detail — and
  contradicts the repository: `tests/integration/` holds six PostgreSQL modules,
  and `.github/workflows/ci.yml:38-128` defines a `PostgreSQL integration` job
  that runs the whole directory against a disposable `nba_test_ci` database.

The rest of both sentences is still correct and must survive: health is liveness
only and takes no Session, and HTTP tests use offline `TestClient` with
dependency overrides and do not need PostgreSQL.

# Human decisions or resources

- None.

# Acceptance criteria

- `.agents/skills/api-fastapi/SKILL.md:33` keeps the liveness rule verbatim and
  replaces the "future task" clause with a pointer to where readiness is
  specified — `docs/architecture/API_CONTRACT.md` for the public shape,
  `docs/architecture/API_ARCHITECTURE.md` for the runtime boundaries. It does not
  restate the contract; a second copy is the drift this card is fixing.
- `docs/architecture/API_ARCHITECTURE.md:58` keeps "app foundation tests do not
  need PostgreSQL" and replaces the "future, separate layer" clause with what
  exists: a PostgreSQL integration lane under `tests/integration/`, gated in CI.
- Neither edit adds a new rule, a new endpoint, or a new constraint. Both are
  corrections of tense and fact only.
- A sweep of `.agents/` and `docs/architecture/` for other "future", "planned",
  or "not yet" claims about readiness, the integration lane, or the PostgreSQL CI
  job finds nothing else stale — or fixes what it finds, in the same change.
  Record what was searched.
- No source file, test, or workflow changes. The offline suite and
  `uv run python scripts/validate_tasks.py` still pass.

# Scope

`.agents/skills/api-fastapi/SKILL.md` and `docs/architecture/API_ARCHITECTURE.md`,
plus any sibling document the sweep proves stale on the same two subjects.

# Out of scope

Rewriting either document. Changing `docs/architecture/API_CONTRACT.md`, which
the audit found accurate. Removing or weakening any shipped feature —
`AGENTS.md` precedence puts the running code above a stale document, so the
document loses. `docs/architecture/SYSTEM_DESIGN.md`'s "Planned Direction"
section, which is genuinely about future work. Anything about the frontend, which
really is future work (F7-001).

# Impact

`.agents/skills/api-fastapi/SKILL.md` is loaded for every card whose `areas`
include `api`, and `docs/architecture/API_ARCHITECTURE.md` is its routed durable
context, so both are read at the start of most API work. Correcting them changes
what every future API card starts from. No runtime behavior changes.

# Implementation notes

Keep the edits minimal and surgical — one clause each. A large rewrite makes the
diff hard to review and risks dropping a rule that is still binding.

`.agents/index.md` routes `api` to this skill plus `API_ARCHITECTURE.md` and
`API_CONTRACT.md`. Check the index itself while you are here; if it too describes
either feature as future, it is part of the same finding.

Do not add a "as of 2026-09" date stamp. The repository's convention is that
durable documents state what is true now, and Git history is the archive.

# Durable knowledge updates

- The two files above are themselves the durable update. Nothing else.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command: `uv run ruff check .`
- Result: `All checks passed!`
- Command: `uv run pytest`
- Result: `949 passed, 27 skipped, 7 warnings in 15.36s`
- Command: `uv run python scripts/validate_tasks.py`
- Result: `Task validation passed.`
- Command: `git diff --check`
- Result: clean (only Git's LF→CRLF working-copy notices).

## Edits

- `.agents/skills/api-fastapi/SKILL.md:33` — liveness rule kept verbatim;
  "Readiness is a separate future task." replaced by a pointer to
  `API_CONTRACT.md` (public shape) and `API_ARCHITECTURE.md` (runtime boundaries).
- `docs/architecture/API_ARCHITECTURE.md:58` — "App foundation tests do not need
  PostgreSQL" kept; "a future, separate layer" replaced by the PostgreSQL lane
  under `tests/integration/`, gated in CI by the `PostgreSQL integration` job.
- Sweep finds, same subject (integration lane), fixed in the same change:
  - `.agents/skills/testing/SKILL.md:12` — "future DB integrations" → the
    PostgreSQL integration lane under `tests/integration/`.
  - `.agents/skills/api-fastapi/references/testing.md:3` — "future real-DB
    integrations" → the real-DB integration lane under `tests/integration/`.

Facts checked before editing: `tests/integration/` holds six test modules
(`test_api_postgres.py`, `test_api_unreachable_database.py`,
`test_preflight_migration_data_postgres.py`,
`test_synthetic_team_code_constraints_postgres.py`,
`test_team_schema_contract_postgres.py`, `test_team_season_loader_postgres.py`);
`.github/workflows/ci.yml:38-39` defines job `postgres-integration` named
`PostgreSQL integration`, running `uv run pytest -ra tests/integration` against
`nba_test_ci`.

## Sweep record

Searched `.agents/**` and `docs/architecture/**` for
`future|planned|not yet|separate task|later task` and for
`readiness|health/ready|integration|PostgreSQL CI|nba_test_ci`.

Remaining hits, judged not stale on readiness / the integration lane / the CI job:
`.agents/index.md` (no such claim); `backlog-planning`, `prepare-task`,
`plan-task` skills ("future critical action" — generic card wording);
`SYSTEM_DESIGN.md:39,94` (genuine future work, out of scope);
`IMPACT_MAP.md:191,204,207` (features/OVR); `PLAYER_PAGE_STATS_MAPPING.md:5`,
`OFFICIAL_STATS_SCHEMA.md:50,516,621,676,678` (stats/parsing subjects);
`API_CONTRACT.md:92` (team-name remediation), `:143` (player routes, genuinely
not yet served in that section; audit found the contract accurate).

## Manual happy path

1. `git diff main -- .agents docs` on this branch.
2. Read `.agents/skills/api-fastapi/SKILL.md` line 33 and follow both pointers.
3. Read `docs/architecture/API_ARCHITECTURE.md` line 58 and compare with
   `ls tests/integration` and the `postgres-integration` job in `.github/workflows/ci.yml`.

Expected result: four one-line changes, each only a tense/fact correction; the
pointers land on the readiness section of `API_CONTRACT.md` and the "Health and
readiness" section of `API_ARCHITECTURE.md`; the described lane and CI job exist.

## Manual sad path

1. `rg -n "future task|future, separate layer|future DB integrations|future real-DB" .agents docs/architecture`
2. `git diff main --stat -- src tests .github alembic scripts`
3. Confirm the liveness sentence in `SKILL.md:33` and "HTTP tests use offline
   `TestClient`..." in `API_ARCHITECTURE.md:58` are unchanged.

Expected result: step 1 returns nothing; step 2 shows no changes; step 3 shows
the still-binding rules intact, with no new rule, endpoint, or constraint added.

## Review decisions

- `.agents/skills/api-fastapi/references/session-lifecycle.md:5` was also stale:
  it called per-app Engine wiring future work that "belongs in F5-002", which
  shipped. It is outside the card's two named subjects but squarely the finding
  this card is titled after, in the same skill folder, so it was fixed here rather
  than split into a card: the sentence now points at the lifespan in
  `src/nba_data/api/app.py`, and the code sample moves Engine creation inside
  `lifespan` to match that file and `API_ARCHITECTURE.md` ("Lifespan builds the
  Engine and the sessionmaker"). The `get_request_session` sample already matched
  `src/nba_data/api/dependencies.py` and was left as is.

## Known limitations

- None.
