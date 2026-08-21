from __future__ import annotations

import pytest
from scripts import preflight_migration_data
from sqlalchemy.sql.elements import TextClause


class FakeResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class FakeConnection:
    def __init__(self, value: int) -> None:
        self.value = value
        self.execution_options_seen: dict[str, object] | None = None
        self.statements: list[TextClause] = []

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def execution_options(self, **options: object) -> FakeConnection:
        self.execution_options_seen = options
        return self

    def execute(self, statement: TextClause) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self.value)


class FakeEngine:
    def __init__(self, value: int) -> None:
        self.connection = FakeConnection(value)
        self.connect_calls = 0
        self.dispose_calls = 0

    def connect(self) -> FakeConnection:
        self.connect_calls += 1
        return self.connection

    def dispose(self) -> None:
        self.dispose_calls += 1


def _install_fake_engine(
    monkeypatch: pytest.MonkeyPatch, null_count: int
) -> tuple[FakeEngine, list[tuple[str, dict[str, object]]]]:
    engine = FakeEngine(null_count)
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_create_engine(url: str, **kwargs: object) -> FakeEngine:
        calls.append((url, kwargs))
        return engine

    monkeypatch.setattr(preflight_migration_data, "create_engine", fake_create_engine)
    return engine, calls


@pytest.mark.unit
@pytest.mark.parametrize(
    ("null_count", "expected_exit_code"),
    [(0, 0), (2, 1)],
    ids=["zero-null-rows", "null-rows"],
)
def test_preflight_reports_count_and_uses_one_read_only_query(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    null_count: int,
    expected_exit_code: int,
) -> None:
    engine, calls = _install_fake_engine(monkeypatch, null_count)
    database_url = "postgresql+psycopg://owner:secret@example.test:5432/nba"

    assert preflight_migration_data.main(["--database-url", database_url]) == expected_exit_code

    # A target that never answers must time out and report, not hang forever.
    assert calls == [
        (
            database_url,
            {
                "connect_args": {
                    "connect_timeout": preflight_migration_data.CONNECT_TIMEOUT_SECONDS
                }
            },
        )
    ]
    assert engine.connect_calls == 1
    assert engine.dispose_calls == 1
    assert engine.connection.execution_options_seen == {"postgresql_readonly": True}
    assert len(engine.connection.statements) == 1
    assert engine.connection.statements[0].text == preflight_migration_data._COUNT_NULL_TEAM_CODES_SQL

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert f"NULL count: {null_count}" in captured.out
    assert preflight_migration_data._TARGET_COLUMN in output
    assert "secret" not in output
    if null_count:
        assert "must not be applied" in captured.err
        assert "Remediation is a separate decision for the user." in captured.err
    else:
        assert "Preflight passed" in captured.out


@pytest.mark.unit
@pytest.mark.parametrize(
    "argv",
    [[], ["--database-url", ""], ["--database-url", "   "]],
    ids=["missing", "empty", "blank"],
)
def test_preflight_refuses_to_run_without_a_named_target(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    """An unnamed target is a usage error, not a database to go and inspect.

    The blank cases matter because `--database-url "$DATABASE_URL"` sends an
    empty string whenever that variable is unset, which `required=True` accepts.
    """

    monkeypatch.setattr(preflight_migration_data, "create_engine", _fail_if_called)

    with pytest.raises(SystemExit) as error:
        preflight_migration_data.main(argv)

    assert error.value.code == 2
    assert "--database-url" in capsys.readouterr().err


@pytest.mark.unit
@pytest.mark.parametrize(
    ("database_url", "expected_message"),
    [
        ("sqlite:///./local.db", "not 'sqlite'"),
        ("not a url at all", "not a database URL SQLAlchemy can parse"),
    ],
    ids=["wrong-backend", "unparseable"],
)
def test_preflight_rejects_a_target_it_could_not_assess(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    expected_message: str,
) -> None:
    """Named as a usage error before connecting, rather than failed after.

    The count reads a PostgreSQL schema through a PostgreSQL-only read-only
    option, so any other backend is a mistake about which database is being
    assessed — the one class of mistake this command exists to prevent.
    """

    monkeypatch.setattr(preflight_migration_data, "create_engine", _fail_if_called)

    with pytest.raises(SystemExit) as error:
        preflight_migration_data.main(["--database-url", database_url])

    assert error.value.code == 2
    assert expected_message in capsys.readouterr().err


def _fail_if_called(url: str, **kwargs: object) -> FakeEngine:
    raise AssertionError(f"create_engine should not run: {url}")
