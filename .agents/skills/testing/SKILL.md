---
name: testing
description: Use when adding or reviewing tests and validation; do not run live scraping or destructive database commands.
---

## Workflow

Run focused offline tests first, then the declared suite. Cover acceptance criteria and report skipped or environment-dependent checks.

## API tasks

Use `TestClient` and dependency overrides with deterministic local fixtures. Test the public contract rather than internals: declared and absent fields, bounds, pagination, and error responses. Clear `app.dependency_overrides`, use `TestClient` as a context manager when lifespan applies, and keep HTTP unit tests separate from future DB integrations.

## Boundaries

Tests must not require network, scraping, production data, or a shared/production database. Validate response schemas, status codes, error limits, and override isolation.
