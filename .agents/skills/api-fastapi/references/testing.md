# API reference: testing

Use `TestClient` as a context manager when lifespan is present. Keep fixtures local and deterministic, clear `app.dependency_overrides`, and split quick offline HTTP tests from future real-DB integrations. Never require PostgreSQL, external network, production data, or scraping for basic HTTP tests.

App foundation coverage: `create_app()` returns FastAPI; multiple app instances and their overrides are isolated; health returns 200 and exactly its approved schema, performs no DB/network work, appears in OpenAPI; mutation and unapproved routes are absent.

Resource coverage: populated and empty collections; existing and missing resources; valid and invalid filters; 422 validation; defined 400 semantic errors; default pagination, maximum and invalid page sizes, post-last-page empty results, correct total and deterministic order; no undeclared ORM fields; and Session/repository overrides.
