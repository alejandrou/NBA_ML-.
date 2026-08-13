"""Readiness against a database address that never answers.

This needs a real socket, so it cannot live in the offline unit lane, but it
contacts nothing outside the machine: `10.255.255.1` is private address space with
no host behind it, chosen because a blackholed address is the case that hangs.
A network that rejects the address outright fails faster and still satisfies the
assertions — only an unbounded connect fails this test.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from nba_data.api import create_app
from nba_data.config.settings import Settings

BLACKHOLE_DATABASE_URL = "postgresql+psycopg://nba:nba@10.255.255.1:5432/nba"
CONNECT_TIMEOUT_SECONDS = 2.0
# Generous next to the 2s bound: this asserts "bounded", not a stopwatch reading,
# so a loaded CI machine cannot turn a real pass into a flake.
GENEROUS_CEILING_SECONDS = 30.0


@pytest.mark.integration
def test_readiness_answers_503_instead_of_hanging_on_an_unreachable_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        database_url=BLACKHOLE_DATABASE_URL,
        database_connect_timeout_seconds=CONNECT_TIMEOUT_SECONDS,
    )
    monkeypatch.setattr("nba_data.db.session.get_settings", lambda: settings)

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        started = time.perf_counter()
        readiness = client.get("/api/v1/health/ready")
        elapsed = time.perf_counter() - started
        liveness = client.get("/api/v1/health")

    assert readiness.status_code == 503
    assert readiness.text == '{"detail":"Database unavailable"}'
    assert elapsed < GENEROUS_CEILING_SECONDS
    assert liveness.status_code == 200
    assert liveness.json() == {"status": "ok"}
