---
name: db-readonly
description: Use for read-only database access and API repository design; do not use for schema changes or writes.
---

Use existing SQLAlchemy models and repositories. Do not mutate sessions, apply
migrations, create records, or trigger scraping. Test query shape and empty
results with local fixtures.
