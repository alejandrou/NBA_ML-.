---
id: F6-016
title: Bind the local database port to loopback by default
areas:
  - documentation
  - testing
priority: 42
depends_on: []
read:
  - docker-compose.yml
  - .env.example
  - README.md
  - scripts/validate_database.sh
  - .github/workflows/ci.yml
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md
validation:
  - docker compose config
  - uv run ruff check .
  - uv run pytest
  - bash scripts/validate_database.sh
critical_actions:
  - Recreating the running `nba_postgres` container to pick up the new binding is the owner's call. The data lives in the named volume `nba_postgres_data` and survives a recreate, but this card neither performs nor authorizes it.
  - Do not delete the `nba_postgres_data` volume or run `docker compose down -v` at any point. That would destroy the ~310 MB archive.
---

# Goal

Stop the development database from listening on every network interface. The
checked-in Compose file publishes PostgreSQL on `0.0.0.0:5432`, which is a
broader default than a local development database needs; it should publish on
the loopback address unless an operator deliberately asks for more.

The network half of finding 2 of
[the 2026-09-08 project and database audit](../../docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md).
The least-privilege database role half is tracked separately as F6-018.

# Evidence and current state

- `docker-compose.yml:9-10` publishes `"${POSTGRES_PORT:-5432}:5432"`. A port
  mapping with no host address binds every interface, and the audit observed the
  running `nba_postgres` container listening on `0.0.0.0` and IPv6 `[::]`, with
  PostgreSQL's own `listen_addresses=*` and SSL disabled.
- `.env.example:8` ships `POSTGRES_PORT=5432` — a port only, with no place to
  express a bind address.
- Nothing depends on the container being reachable from another host. Every
  consumer connects over loopback: `.env.example:1` and
  `src/nba_data/config/settings.py:15` both default to
  `postgresql+psycopg://nba:nba@localhost:5432/nba`, `scripts/validate_database.sh`
  reaches the container through `docker compose exec`, and
  `docs/validation/OFFLINE_DATABASE_PREPARATION.md:23` documents the same
  loopback URL.
- CI does not use this file. `.github/workflows/ci.yml:54-61` defines its own
  GitHub Actions `services: postgres` block with its own `"5432:5432"` mapping
  against a disposable `nba_test_ci` database, so this change cannot affect the
  CI lane.
- The audit did not test firewall reachability and did not find the database
  publicly accessible. This is a default worth tightening, not an observed
  exposure.

# Human decisions or resources

- [x] Whether an operator may still publish more broadly: yes — the bind address
      becomes an environment variable with a loopback default, exactly as
      `POSTGRES_PORT` is a variable with a `5432` default. Nothing becomes
      impossible; the unsafe option stops being the default.

# Acceptance criteria

- `docker-compose.yml` publishes the database on the loopback address by default,
  through a variable an operator can override — for example
  `"${POSTGRES_BIND_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}:5432"`. `POSTGRES_PORT`
  keeps its current meaning and its `5432` default.
- `.env.example` gains the new variable with the loopback default and a one-line
  comment saying what widening it does. The file stays a complete, working
  example.
- `docker compose config` renders the intended mapping with no variables set, and
  renders the widened mapping when the new variable is set. Record both renderings
  in the review evidence.
- `README.md`'s setup section states that `docker compose up -d postgres`
  publishes on loopback only, and how to change it. One or two sentences, not a
  section.
- `bash scripts/validate_database.sh` still passes: it brings the container up,
  creates its disposable database, round-trips the migrations, and cleans up.
- No source file, test, connection string, or CI workflow changes. The default
  `DATABASE_URL` still works unchanged, because it was already `localhost`.

# Scope

`docker-compose.yml`, `.env.example`, and the setup section of `README.md`.

# Out of scope

The database role and privilege half of finding 2 — that is F6-018. PostgreSQL's
own `listen_addresses` inside the container, which is reached only through the
published port and is not what limits exposure here. TLS between the client and
the database. Changing credentials, the default password, or anything in `.env`.
The CI services block. Recreating the running container.

# Impact

Anyone who currently reaches this database from another machine — a second
device, a VM, a container on another network — loses that reach until they set
the new variable. The audit found no such consumer in the repository, but the
owner's own habits are not visible to it, so say this plainly in the review
evidence rather than assuming.

The change takes effect only when the container is recreated. Until then, the
running `nba_postgres` keeps its current binding.

# Implementation notes

Compose's long-form `ports` syntax takes an explicit `host_ip`; the short form
takes `HOST:PORT:CONTAINER`. Either is acceptable — pick the one that keeps
`docker compose config` output easy to read, and keep the healthcheck untouched.

Use `docker compose config` to verify. It renders the merged configuration and
starts nothing, so it is safe to run repeatedly.

`127.0.0.1` binds IPv4 loopback only; a client resolving `localhost` to `::1`
would then fail. Check that the default `DATABASE_URL` still connects on this
machine before calling the card done, and if IPv6 matters here, say so in the
review evidence rather than silently widening the binding again.

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — only if its `docker compose
  up` instructions become inaccurate.

# Review evidence

## Automated validation

- Command: `docker compose config` with no variables set
- Result: passed. Renders `host_ip: 127.0.0.1`, `published: "5432"`,
  `target: 5432`, `protocol: tcp`.

- Command: `POSTGRES_BIND_HOST=0.0.0.0 POSTGRES_PORT=5433 docker compose config`
- Result: passed. Renders `host_ip: 0.0.0.0`, `published: "5433"` — the operator
  override works and `POSTGRES_PORT` keeps its independent meaning.

- Command: `uv run ruff check .`
- Result: passed. `All checks passed!`

- Command: `uv run pytest`
- Result: passed. 892 passed, 27 skipped, 7 warnings in 20.57s.

- Command: `uv run python scripts/validate_tasks.py`
- Result: passed. `Task validation passed.`

- Command: `bash scripts/validate_database.sh`
- Result: passed, exit code 0. Brought the container up, created
  `nba_test_tmp_788ee423c6664ecf`, ran `0007 -> 0008`, the `0008` downgrade
  (raw schema catalog exactly restored), the unrecognized-raw-object rejection,
  `upgrade head`, `alembic check`, then 28 integration tests in 405s, and dropped
  the temporary database. Zero `nba_test_tmp%` databases remain. The 405s is the
  freshly recreated container running cold, not a regression from this card; the
  same lane took seconds against the warm container before the recreate.

- Command: connect to the default `DATABASE_URL`
  (`postgresql+psycopg://nba:nba@localhost:5432/nba`) after the recreate
- Result: passed. Connected, 41 application tables, 310 MB, `alembic_version` at
  `0008_drop_raw_schema`. The archive is intact.

## Manual happy path

1. Confirm the default binding with nothing set:

   ```bash
   docker compose config
   ```

   Expected result: the `ports` entry shows `host_ip: 127.0.0.1` and
   `published: "5432"`.

2. Confirm the running container picked it up:

   ```bash
   docker ps --filter name=nba_postgres --format "{{.Ports}}"
   ```

   Expected result: `127.0.0.1:5432->5432/tcp` — one mapping, no `0.0.0.0`, no
   `[::]`. Before this card it was `0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp`.

3. Confirm the application still connects unchanged:

   ```bash
   uv run python -c "from sqlalchemy import create_engine, text; e = create_engine('postgresql+psycopg://nba:nba@localhost:5432/nba'); c = e.connect(); print(c.execute(text('select 1')).scalar())"
   ```

   Expected result: prints `1`. No connection string anywhere changed, because
   every consumer was already on `localhost`.

Expected result: the database is published on loopback only, and every local
consumer works exactly as before.

## Manual sad path

1. Ask for the old, wide binding explicitly and confirm it is still available:

   ```bash
   POSTGRES_BIND_HOST=0.0.0.0 docker compose config
   ```

   Expected result: `host_ip: 0.0.0.0`. The wide option was not removed — it
   stopped being the default. Nothing is applied; `docker compose config` renders
   and starts nothing.

2. Confirm the port is no longer served on a non-loopback interface, from the
   host, with the container running under the new binding:

   ```bash
   powershell -Command "Test-NetConnection -ComputerName (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' } | Select-Object -First 1).IPAddress -Port 5432 -InformationLevel Quiet"
   ```

   Expected result: `False`. The same probe against `127.0.0.1` returns `True`.

3. Confirm a stale `.env` cannot silently re-widen the binding. `.env.example`
   ships `POSTGRES_BIND_HOST=127.0.0.1`; an existing `.env` written before this
   card has no such key.

   Expected result: the Compose default `127.0.0.1` applies, so an old `.env`
   gets the safe binding rather than the old wide one.

Expected result: widening stays possible and deliberate; forgetting to decide
gets loopback.

## Known limitations

- **The IPv4-only question was tested, not assumed.** `127.0.0.1` binds IPv4
  loopback only, and on this machine `localhost` resolves to `::1` first
  (`getaddrinfo` returns `::1` then `127.0.0.1`). A disposable probe container
  published on `127.0.0.1:5433` still accepted
  `postgresql+psycopg://...@localhost:5433/...`, confirming libpq walks past the
  refused `::1` to the IPv4 address. The probe was removed. If some future client
  does not fall back, the fix is `POSTGRES_BIND_HOST=::1` or a second mapping —
  not reverting to a wide default.
- **Reach from another machine is gone until the variable is set.** Anyone using
  this database from a second device, a VM, or a container on another network
  loses it until they set `POSTGRES_BIND_HOST`. The audit found no such consumer
  in the repository, and none exists in the code, but the repository cannot see
  the owner's own habits.
- **The container was recreated** under the owner's direct instruction during this
  card. `nba_postgres` now reports `127.0.0.1:5432->5432/tcp`. The
  `nba_postgres_data` volume was never deleted and `docker compose down -v` was
  never run; the 310 MB archive verified intact at 41 tables afterwards.
- **PostgreSQL's own `listen_addresses` is still `*`** inside the container, and
  SSL is still disabled. Neither is what limits exposure here — the published
  port is — and both are explicitly out of scope. The privilege half of audit
  finding 2 remains open as F6-018.
- **`docs/validation/OFFLINE_DATABASE_PREPARATION.md` was not touched.** Its
  `docker compose up -d postgres` instruction and its `localhost` URL are both
  still accurate, which was the card's stated condition for editing it.
- **This card did not pass through `tasks/review/`.** It was moved from
  `tasks/active/` straight to `tasks/done/` by the owner, so this evidence was
  written after the move rather than before it.
