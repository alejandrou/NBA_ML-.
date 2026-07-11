---
name: api-fastapi
description: Use for FastAPI APIs, routers, endpoints, schemas, TestClient, or HTTP contracts; do not use for scraping or database migrations.
---

## Use when

Designing or implementing the approved read-only FastAPI surface.

## Do not use when

The task is only scraping, migrations, frontend work, or generated metrics.

## Inputs

Read the active task card, API architecture/contract docs, and only its
declared references.

## Workflow

1. Confirm the task is in the approved API phase.
2. Keep the base path `/api/v1` and GET-only boundary.
3. Put the app factory in `src/nba_data/api/app.py`, routers in
   `routers/`, schemas in `schemas/`, and services in `services/`.
4. Use dependency injection and repository reads; keep routers small.
5. Add TestClient coverage for status, response shape, errors, and pagination.

## Required patterns

Use Pydantic response models, typed filters, bounded pagination, explicit HTTP
errors, and router/service/repository separation. Do not expose ORM objects.

## Forbidden actions

No POST/PUT/PATCH/DELETE, database writes, scraping, auth, migrations, or
unapproved business endpoints.

## Validation

Run the task-card lint and test commands.

## Expected output

A narrow contract-compliant API change with focused tests and no side effects.

## References

Load `references/architecture.md`, `references/testing.md`, or
`references/errors-and-pagination.md` only when needed.
