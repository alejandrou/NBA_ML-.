"""The retired prototype cannot reach the platform database (DATABASE_AUDIT_2026-11-10, R-05)."""

from __future__ import annotations

import asyncio

import pytest
import scrape_main
from db_manager import db_conf
from db_manager.db_manager import DBManager
from peewee import InterfaceError


@pytest.fixture(autouse=True)
def _uninitialized_legacy_database() -> None:
    db_conf.db.init(None)


@pytest.mark.unit
def test_the_legacy_database_has_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEGACY_POSTGRES_DB", raising=False)
    monkeypatch.setenv("POSTGRES_DB", "nba")  # the old default source is ignored

    with pytest.raises(RuntimeError, match="no default database"):
        DBManager.connect_db()


@pytest.mark.unit
@pytest.mark.parametrize("name", ["nba", "NBA", " nba "])
def test_the_platform_database_is_refused(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEGACY_POSTGRES_DB", name)

    with pytest.raises(RuntimeError, match="may not write the platform database"):
        DBManager.connect_db()


@pytest.mark.unit
def test_table_creation_without_configuration_fails_before_connecting() -> None:
    with pytest.raises(InterfaceError, match="must be initialized"):
        db_conf.db.connect()


@pytest.mark.unit
def test_the_legacy_entrypoint_refuses_to_run() -> None:
    with pytest.raises(SystemExit, match="retired"):
        asyncio.run(scrape_main.main())
