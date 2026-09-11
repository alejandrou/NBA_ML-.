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
