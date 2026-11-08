"""`nba-data ml evaluate`: wires the reader and paths, reports failure, loads no ML at startup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from nba_data.cli import main
from nba_data.ml import evaluation, team_games
from nba_data.ml.artifact import ArtifactConflictError

runner = CliRunner()


class _FakeEngine:
    disposed = False

    def dispose(self) -> None:
        self.disposed = True


class _FakeSession:
    options: dict[str, Any] | None = None

    def connection(self, execution_options: dict[str, Any]) -> None:
        type(self).options = execution_options

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> _FakeEngine:
    fake = _FakeEngine()
    monkeypatch.setattr(main, "create_db_engine", lambda settings: fake)
    monkeypatch.setattr(main, "create_session_factory", lambda engine: _FakeSession)
    return fake


def _arguments(tmp_path: Path) -> list[str]:
    output, models = str(tmp_path / "report.json"), str(tmp_path / "models")
    return ["ml", "evaluate", "--output", output, "--artifact-dir", models]


def test_evaluate_reads_through_the_requested_season_and_prints_the_summary(
    engine: _FakeEngine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, Any] = {}

    def fake_run(read_games: Any, *, output: Path, artifact_dir: Path) -> dict[str, Any]:
        calls["games"] = read_games(2025)
        calls["paths"] = (output, artifact_dir)
        return {"selected": "elo", "stage_5_go": True}

    def fake_load(session: object, *, through_season: int) -> list[str]:
        return [f"through {through_season}"]

    monkeypatch.setattr(evaluation, "run_and_publish", fake_run)
    monkeypatch.setattr(team_games, "load_team_game_history", fake_load)

    result = runner.invoke(main.app, _arguments(tmp_path))

    assert result.exit_code == 0, result.output
    assert '"selected": "elo"' in result.output
    assert calls["games"] == ["through 2025"]
    assert _FakeSession.options == {
        "isolation_level": "REPEATABLE READ",
        "postgresql_readonly": True,
    }
    assert calls["paths"] == (tmp_path / "report.json", tmp_path / "models")
    assert engine.disposed


@pytest.mark.parametrize(
    "error", [ValueError("no usable games"), ArtifactConflictError("different content")]
)
def test_a_failed_evaluation_exits_non_zero_and_names_the_reason(
    engine: _FakeEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    def failing_run(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(evaluation, "run_and_publish", failing_run)

    result = runner.invoke(main.app, _arguments(tmp_path))

    assert result.exit_code == 1
    assert str(error) in result.output
    assert engine.disposed


def test_both_paths_are_required(tmp_path: Path) -> None:
    result = runner.invoke(main.app, ["ml", "evaluate", "--output", str(tmp_path / "r.json")])

    assert result.exit_code != 0


@pytest.mark.parametrize(
    "arguments",
    [
        ["ml", "register-model", "somewhere"],
        ["ml", "activate", "somewhere"],
        ["ml", "predict", "--from", "2026-12-01", "--to", "2026-12-02"],
    ],
)
def test_ml_writes_are_refused_before_an_engine_exists(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    def refused(database_url: str) -> None:
        raise main.LoadTargetError("Refusing to load persistent database 'nba'")

    def no_engine(settings: object) -> None:
        raise AssertionError("an engine was created")

    monkeypatch.setattr(main, "require_load_target", refused)
    monkeypatch.setattr(main, "create_db_engine", no_engine)

    result = runner.invoke(main.app, arguments)

    assert result.exit_code == 1
    assert "Refusing to load" in result.output


def test_starting_the_cli_does_not_load_the_numerical_stack() -> None:
    code = (
        "import sys\n"
        "import nba_data.cli.main\n"
        "print([name for name in sys.modules if name.split('.')[0] in ('sklearn', 'numpy')])\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=60
    )

    assert result.stdout.strip() == "[]"
