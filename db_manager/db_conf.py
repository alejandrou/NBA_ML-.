"""Legacy Peewee database of the retired prototype (ADR 0002).

It used to default to the `nba` database, where `create_tables` would have added
prototype tables to `public` (DATABASE_AUDIT_2026-11-10, R-05). It now has no
default: `db` is deferred, so nothing can connect until
`configure_legacy_database()` is given a database in `LEGACY_POSTGRES_DB`, and
that database may not be the platform's own.
"""

import os

from peewee import PostgresqlDatabase

PROTECTED_DATABASES = frozenset({"nba"})

db = PostgresqlDatabase(None)


def configure_legacy_database() -> None:
    name = os.getenv("LEGACY_POSTGRES_DB", "").strip()
    if not name:
        msg = "The legacy prototype has no default database; set LEGACY_POSTGRES_DB to a scratch one."
        raise RuntimeError(msg)
    if name.lower() in PROTECTED_DATABASES:
        msg = f"The legacy prototype may not write the platform database {name!r}."
        raise RuntimeError(msg)
    db.init(
        name,
        user=os.getenv("POSTGRES_USER", "nba"),
        password=os.getenv("POSTGRES_PASSWORD", "nba"),
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
    )
