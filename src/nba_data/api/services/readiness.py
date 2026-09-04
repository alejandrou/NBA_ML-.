"""Database readiness probe backing `GET /api/v1/health/ready`.

The probe converts every failure into an outcome instead of raising: the app
registers a catch-all `Exception` handler that answers 500, and readiness must
answer 503. Escaping to that handler is a defect, not a fallback.
"""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

REQUIRED_SCHEMA = "core"
REQUIRED_TABLES: tuple[str, ...] = ("teams", "seasons")

# Resolved from this package, never from the process working directory: a
# relative path here would silently resolve against wherever the server happens
# to be started (the F4E-011 failure mode).
ALEMBIC_INI_PATH = Path(__file__).resolve().parents[4] / "alembic.ini"

_QUERY_CANCELED_SQLSTATE = "57014"


class ReadinessOutcome(Enum):
    """Distinct causes, so the router never inspects exception text."""

    READY = "ready"
    UNAVAILABLE = "unavailable"
    TIMED_OUT = "timed_out"
    SCHEMA_NOT_READY = "schema_not_ready"


def check_database_readiness(session: Session, *, timeout_seconds: float) -> ReadinessOutcome:
    """Report whether the database is reachable, at the migration head, and stocked."""
    try:
        return _probe(session, timeout_seconds=timeout_seconds)
    except OperationalError as exc:
        if _is_query_canceled(exc):
            logger.warning(
                "Readiness probe exceeded its %ss bound", timeout_seconds, exc_info=exc
            )
            return ReadinessOutcome.TIMED_OUT
        logger.warning("Readiness probe could not reach the database", exc_info=exc)
        return ReadinessOutcome.UNAVAILABLE
    except SQLAlchemyError as exc:
        logger.warning("Readiness probe could not read the database schema", exc_info=exc)
        return ReadinessOutcome.SCHEMA_NOT_READY
    except Exception:
        # Nothing may escape to the 500 handler, so an unforeseen failure still
        # reports the honest operator-facing answer: the database is not usable.
        logger.exception("Readiness probe failed unexpectedly")
        return ReadinessOutcome.UNAVAILABLE


def _probe(session: Session, *, timeout_seconds: float) -> ReadinessOutcome:
    _bound_probe(session, timeout_seconds=timeout_seconds)
    session.execute(text("SELECT 1"))

    applied = set(session.scalars(text("SELECT version_num FROM alembic_version")).all())
    heads = set(migration_heads())
    if applied != heads:
        logger.warning(
            "Database is at Alembic revision(s) %s, not the migration head(s) %s",
            sorted(applied),
            sorted(heads),
        )
        return ReadinessOutcome.SCHEMA_NOT_READY

    missing = _missing_required_tables(session)
    if missing:
        logger.warning("Database is missing required table(s): %s", ", ".join(missing))
        return ReadinessOutcome.SCHEMA_NOT_READY

    return ReadinessOutcome.READY


def _bound_probe(session: Session, *, timeout_seconds: float) -> None:
    """Bound the probe in the database, so a server that stops answering cannot hang us."""
    if session.get_bind().dialect.name != "postgresql":
        return

    milliseconds = max(1, int(timeout_seconds * 1000))
    # PostgreSQL rejects bound parameters in SET; the value is a computed
    # integer derived from configuration, never from request input.
    session.execute(text(f"SET LOCAL statement_timeout = {milliseconds}"))


def _missing_required_tables(session: Session) -> list[str]:
    present = set(
        session.scalars(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
            {"schema": REQUIRED_SCHEMA},
        ).all()
    )
    return [f"{REQUIRED_SCHEMA}.{name}" for name in REQUIRED_TABLES if name not in present]


def _is_query_canceled(exc: DBAPIError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == _QUERY_CANCELED_SQLSTATE


@lru_cache(maxsize=1)
def migration_heads() -> tuple[str, ...]:
    """Return the Alembic head revision(s) shipped with this package.

    Migration scripts are static program files, so resolving them once is safe.
    The database state they are compared against is read on every request and is
    never cached.
    """
    config = Config(str(ALEMBIC_INI_PATH))
    script_location = config.get_main_option("script_location") or "alembic"
    config.set_main_option(
        "script_location", str((ALEMBIC_INI_PATH.parent / script_location).resolve())
    )
    # `from_config` would otherwise splice the ini's relative `prepend_sys_path`
    # entries into a running server's `sys.path`, reintroducing the working
    # directory this module deliberately avoids.
    config.set_main_option("prepend_sys_path", "")

    return tuple(ScriptDirectory.from_config(config).get_heads())
