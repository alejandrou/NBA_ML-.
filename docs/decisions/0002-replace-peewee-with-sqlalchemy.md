# ADR 0002 - Replace Peewee with SQLAlchemy

## Status

Accepted

## Context

The prototype uses Peewee and direct table creation.

## Decision

Use SQLAlchemy 2.0 for all new database code and migrate Peewee progressively.

## Consequences

Legacy Peewee remains until migrated. No new Peewee code should be added.

**Removal gate.** Remove Peewee only once equivalent SQLAlchemy loaders and
migrations exist for what it still covers. Until then `models/`, `db_manager/`,
`scrap/`, and `scrape_main.py` stay read-only.

**Known debt carried by the legacy stack**, to be resolved by whatever card
finally retires it: `db_manager/db_conf.py` holds credentials in code; players
are matched by name rather than by a stable identifier; the legacy scrapers issue
direct HTTP requests instead of going through the rate-limited client.

## Alternatives Considered

- Keep Peewee permanently: lower immediate effort but weaker migration story.
- Rewrite everything now: too risky for Phase 1.
