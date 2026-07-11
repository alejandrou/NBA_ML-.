# API architecture

Phase 5 will add a read-only FastAPI surface over stable database data. The
initial boundary is `/api/v1`; endpoints are GET-only, do not scrape, do not
write to the database, and do not require authentication.

The planned package layout is `src/nba_data/api/app.py`, `routers/`,
`schemas/`, and `services/`. Routers translate HTTP concerns, services hold
use-case orchestration, and repositories perform read-only persistence access.
ORM models are not exposed directly; Pydantic response models define the
contract. Dependencies provide sessions and services. Collections use explicit
pagination and typed filters. TestClient tests cover the HTTP boundary.

Phase 5 does not include frontend, scraping triggers, mutations, migrations,
rankings, OVR, similarity, or ML.
