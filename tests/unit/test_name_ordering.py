"""List order does not depend on the server's OS locale (DATABASE_AUDIT_2026-11-10, R-07)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite

from nba_data.db.models.core import Player
from nba_data.db.repositories.queries.ordering import portable_name_order


def _session(dialect_name: str) -> object:
    return SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name=dialect_name)))


@pytest.mark.unit
def test_postgresql_orders_names_by_icu_root_collation() -> None:
    order = portable_name_order(_session("postgresql"), Player.full_name)  # type: ignore[arg-type]

    sql = str(select(Player.id).order_by(order).compile(dialect=postgresql.dialect()))

    assert 'ORDER BY core.players.full_name COLLATE "und-x-icu"' in sql


@pytest.mark.unit
def test_other_databases_keep_their_own_fixed_order() -> None:
    order = portable_name_order(_session("sqlite"), Player.full_name)  # type: ignore[arg-type]

    sql = str(select(Player.id).order_by(order).compile(dialect=sqlite.dialect()))

    assert "COLLATE" not in sql
