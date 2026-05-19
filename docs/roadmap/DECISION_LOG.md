# Decision Log

## Decision

Initial scope is NBA only.

### Context

The project may support more leagues in the future, but the first target is NBA.

### Decision Taken

Use `league = NBA` as the initial scope and design for future extension.

### Reason

NBA focus keeps Phase 1 small and matches the current prototype.

### Consequences

ABA and other leagues remain out of scope.

## Decision

Use `uv`.

### Context

The repository has no existing package manager integration.

### Decision Taken

Use `pyproject.toml` with `uv`.

### Reason

`uv` gives fast dependency and tool execution.

### Consequences

Developer setup uses `uv sync` and `uv run`.

## Decision

Cache raw HTML as local `.html.gz`.

### Context

Scraping should avoid duplicate downloads and preserve source HTML.

### Decision Taken

Store raw HTML compressed on disk and store metadata in PostgreSQL later.

### Reason

Local compressed files are simple, cheap, and inspectable.

### Consequences

Object storage is deferred.

## Decision

Use conservative Basketball Reference rate limits.

### Context

Sports Reference can block sessions for excessive requests.

### Decision Taken

Default to 10 requests/minute and never exceed 20 requests/minute.

### Reason

This protects the project and respects the site.

### Consequences

Scraping jobs will be slower but safer.

## Decision

Deprecate Peewee progressively.

### Context

The prototype uses Peewee models and direct table creation.

### Decision Taken

Do not add new Peewee code. New code uses SQLAlchemy and Alembic.

### Reason

SQLAlchemy/Alembic better supports a long-term data platform.

### Consequences

Legacy code remains until migrated.

## Decision

Use repo-scoped skills and roles.

### Context

The owner wants the repository to guide agents without relying on chat memory.

### Decision Taken

Store skills under `.agents/skills/` and roles under `.agents/roles/`.

### Reason

This makes workflows portable and reviewable.

### Consequences

Future work should start by reading `AGENTS.md` and the relevant skill.

## Decision

Use progress memory.

### Context

The project needs state that survives chat sessions.

### Decision Taken

Store active work, history, blockers, review notes, and research in `progress/`.

### Reason

This makes handoff and owner learning easier.

### Consequences

Agents must update progress after each checkpoint.

## Decision

Use a structured feature list.

### Context

Tasks need consistent status, scope, acceptance criteria, and validation.

### Decision Taken

Use `tasks/feature-list.json`.

### Reason

JSON is easy for humans to inspect and agents to update.

### Consequences

Task status changes should be reflected in the JSON file.

## Decision

No API, frontend, OVR, or historical scraping in Phase 1.

### Context

The project needs foundations before user-facing features.

### Decision Taken

Phase 1 only adds harness, setup, client, cache, parser pattern, DB foundation,
tests, and CI.

### Reason

Small scope reduces risk and keeps learning clear.

### Consequences

Phase 2 can safely adapt the existing scraper pipeline.
