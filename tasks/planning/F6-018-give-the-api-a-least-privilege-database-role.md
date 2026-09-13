---
id: F6-018
title: Give the API a least-privilege database role
track: app
areas:
  - planning
  - api
  - database-read
  - database-schema
  - documentation
priority: 41
depends_on: []
read:
  - src/nba_data/config/settings.py
  - src/nba_data/db/session.py
  - src/nba_data/api/app.py
  - src/nba_data/api/dependencies.py
  - src/nba_data/api/services/readiness.py
  - docs/architecture/API_ARCHITECTURE.md
  - docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md
  - .github/workflows/ci.yml
  - .env.example
validation: []
critical_actions:
  - Creating a role or granting privileges on the persistent `nba` database is a critical action needing the owner's direct, current instruction. This card authorizes nothing.
  - Any provisioning script must be reversible and must never alter existing data, ownership of existing objects, or the `nba` role itself.
---

# Goal

Decide whether the read-only API should connect as a dedicated SELECT-only
database role instead of the superuser it shares with the loaders, and settle the
configuration shape that would require.

The privilege half of finding 2 of
[the 2026-09-08 project and database audit](../../docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md).
The network half is F6-016, which is ready and independent.

This card stays in `tasks/planning/` because the answer is a design decision
about the platform's public configuration surface, not something the code can be
read to discover.

# Evidence and current state

- The audit found exactly one non-system role in the database: `nba`, a superuser
  with role- and database-creation privileges and write privileges on all 44
  tables.
- Every component connects as that role through one setting.
  `src/nba_data/config/settings.py:15` defaults `database_url` to
  `postgresql+psycopg://nba:nba@localhost:5432/nba`;
  `src/nba_data/db/session.py:29-36` builds the single Engine from it; and
  `src/nba_data/api/app.py:22-25` creates that Engine once per app in lifespan.
  The API, the CLI, the loaders, and Alembic all read the same value.
- The API's read-only behavior is therefore a property of its code, not of its
  credentials. The architecture already enforces it at three layers:
  `docs/architecture/API_ARCHITECTURE.md` restricts API reads to the dedicated
  query repositories in `db/repositories/queries/`, which are read-only and never
  mutate their Session; `src/nba_data/api/dependencies.py:9-13` yields a
  request-scoped Session and never commits; and the HTTP surface is GET-only.
  The audit found no write path in the inspected API flow.
- So this is defence in depth against a future mistake, not a fix for an observed
  write. Nothing in the audit shows the API writing anything.
- CI would be affected: `.github/workflows/ci.yml:47` gives the integration lane a
  single `DATABASE_URL` pointing at a disposable `nba_test_ci` database, and the
  lane both migrates and loads through it.
- Readiness reads `alembic_version`, `information_schema.tables`, and runs
  `SET LOCAL statement_timeout` (`src/nba_data/api/services/readiness.py:65-105`).
  A SELECT-only role must still be able to do all three, which is a real
  constraint on any grant script.

# Human decisions or resources

- [ ] Is the separation worth its operational cost at all? It adds a role to
      provision, a second URL to configure, and a new way for the API to fail
      (missing grant on a newly added table) in exchange for a guarantee the code
      already provides. Declining is a legitimate answer — record it as a decision
      rather than leaving the finding open.
- [ ] If yes: does the API get a new setting (`api_database_url`, defaulting to
      `database_url` when unset), or does the operator simply point `DATABASE_URL`
      at the read-only role for the API process and at the owning role for the CLI?
      The first changes the public configuration surface and the app factory; the
      second changes only documentation and deployment habits.
- [ ] How is the role provisioned and kept correct? A checked-in SQL script the
      owner runs, an Alembic revision, or a documented `psql` snippet. Whichever
      is chosen must also answer what happens when a migration adds a table:
      `ALTER DEFAULT PRIVILEGES` covers future objects created by one role, and
      the answer determines whether a new table silently becomes unreadable to the
      API.
- [ ] Does the CI integration lane use the read-only role too? Testing the grants
      is most of their value, but the lane migrates and loads, so it would need
      two URLs and a provisioning step.
- [ ] Is transport protection in scope? The audit noted SSL is disabled. Over
      loopback that is defensible; if the answer to F6-016 ever widens the
      binding, it stops being.

# Acceptance criteria

Cannot be fixed until the decisions above are settled. The shape they will take:

- a named role with `CONNECT` on the database, `USAGE` on `core` and `stats`, and
  `SELECT` on their tables — and nothing else;
- readiness still answers 200 as that role, including its `alembic_version` read,
  its `information_schema` read, and its `SET LOCAL statement_timeout`;
- an integration test proving the role cannot `INSERT`, `UPDATE`, `DELETE`, or
  `CREATE`, in the spirit of
  `tests/integration/test_preflight_migration_data_postgres.py`'s
  `test_the_preflight_connection_cannot_write_to_the_target`;
- a documented, reversible provisioning path;
- the loaders, the CLI, and Alembic keep the privileges they need.

# Scope

To be fixed when the card is prepared. Expected to touch configuration, the
session/app wiring if a second URL is chosen, a provisioning artifact, the
integration lane, and the setup documentation.

# Out of scope

The Compose port binding, which is F6-016. Rotating or changing any credential.
Anything in `.env`. Making the API's code less read-only on the grounds that the
role now enforces it — the layers are cumulative, not alternatives. Remote access,
authentication, and authorization for the HTTP surface.

# Impact

Reaches the app factory, the settings surface, the integration lane, CI, and the
setup instructions, and adds a provisioning step to any new environment. Because
it changes how the platform is configured, it is likely to need splitting into a
provisioning card and a wiring card once the decisions land.

# Implementation notes

Do not promote this card by guessing an answer. `prepare-task` should resolve
what the code can settle — which grants readiness actually needs, whether CI can
carry two URLs — and leave the rest to the owner.

If the answer is "not worth it", the useful deliverable is a short ADR recording
why the code-level read-only guarantee is considered sufficient, so the same
finding is not re-raised by the next audit.

The card is `track: app`, but role provisioning is `database-schema` work that
belongs to the `data` track (ADR 0018). When preparing it, either split the
provisioning into its own `data` card that this one depends on, or mark the
whole card `shared`; a `track: app` card cannot reach `tasks/backlog/` while it
keeps the `database-schema` area.

# Durable knowledge updates

- Likely an ADR under `docs/decisions/`, whichever way the decision goes.
- `docs/architecture/API_ARCHITECTURE.md`, if the API gains its own connection
  identity.

# Review evidence

Filled in before the card moves to `tasks/review/`.

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
