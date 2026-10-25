"""Connection policy for the disposable lane, without opening a socket."""

import subprocess

import pytest
from scripts import validate_postgres_local as runner
from sqlalchemy.engine import make_url


@pytest.mark.unit
def test_local_validation_uses_ipv4_and_bounds_child_connections() -> None:
    url = runner._validation_url(make_url("postgresql+psycopg://user@localhost/nba"))
    assert url.host == "localhost"
    assert url.query["hostaddr"] == "127.0.0.1"
    assert int(url.query["connect_timeout"]) >= 2
    assert url.set(database="nba_test_tmp_example").query == url.query


@pytest.mark.unit
@pytest.mark.parametrize("host", ["localhost", "db.internal"])
def test_validation_preserves_explicit_connection_overrides(host: str) -> None:
    original = make_url(
        f"postgresql+psycopg://user@{host}/nba?hostaddr=127.0.0.2&connect_timeout=4"
    )
    assert runner._validation_url(original) == original


@pytest.mark.unit
def test_validation_does_not_redirect_remote_hosts() -> None:
    url = runner._validation_url(make_url("postgresql+psycopg://user@db.internal/nba"))
    assert "hostaddr" not in url.query
    assert "connect_timeout" in url.query


@pytest.mark.unit
def test_validation_step_timeout_fails_instead_of_hanging(monkeypatch: pytest.MonkeyPatch) -> None:
    def timed_out(command: list[str], **kwargs: object) -> None:
        assert kwargs["timeout"] == 600
        raise subprocess.TimeoutExpired(command, 600)

    monkeypatch.setattr(runner.subprocess, "run", timed_out)
    assert runner._run({}, ["uv", "run", "alembic", "check"]) == 1
