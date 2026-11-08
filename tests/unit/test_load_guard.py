"""The guard on the two current-season load commands: refusals happen before any connection."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import nba_data.cli.main as cli_main
from nba_data.db.load_guard import LoadTargetError, require_load_target

PERSISTENT = "postgresql+psycopg://user:pw@localhost:5432/nba"
DISPOSABLE = "postgresql+psycopg://user:pw@localhost:5432/nba_test_tmp_abc"
COMMANDS = (
    ["backfill", "current-season-identity", "--season", "2027"],
    ["backfill", "current-season-games", "--season", "2027", "--as-of", "2026-11-08"],
)
APPROVAL = "--execute-approved-current-season-load"


def _git(*, merged: int = 0, porcelain: str = "", status_code: int = 0):  # type: ignore[no-untyped-def]
    def run(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if arguments[0] == "merge-base":
            return subprocess.CompletedProcess(arguments, merged, "", "")
        return subprocess.CompletedProcess(arguments, status_code, porcelain, "")

    return run


@pytest.mark.unit
def test_a_disposable_database_needs_no_git_check() -> None:
    def fail(_arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise AssertionError("git must not run")

    require_load_target(DISPOSABLE, git=fail)


@pytest.mark.unit
def test_a_persistent_database_passes_from_a_clean_merged_checkout() -> None:
    require_load_target(PERSISTENT, git=_git())


@pytest.mark.unit
@pytest.mark.parametrize(
    ("git", "reason"),
    [
        (_git(merged=1), "not on origin/main"),
        (_git(merged=128), "not on origin/main"),
        (_git(porcelain=" M src/nba_data/cli/main.py\n"), "uncommitted"),
        (_git(status_code=128), "uncommitted"),
    ],
)
def test_a_persistent_database_is_refused_from_other_checkouts(git, reason: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(LoadTargetError, match=reason):
        require_load_target(PERSISTENT, git=git)


@pytest.mark.unit
def test_a_checkout_that_cannot_be_inspected_is_refused() -> None:
    def missing(_arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    with pytest.raises(LoadTargetError, match="cannot inspect"):
        require_load_target(PERSISTENT, git=missing)


@pytest.fixture
def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the command connected to the database")

    monkeypatch.setattr(cli_main, "create_db_engine", refuse)
    settings = SimpleNamespace(database_url=PERSISTENT, log_level="INFO")
    monkeypatch.setattr(cli_main, "get_settings", lambda: settings)


@pytest.mark.unit
@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.usefixtures("no_database")
def test_each_command_refuses_without_the_approval_flag(command: list[str]) -> None:
    result = CliRunner().invoke(cli_main.app, command)

    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)


@pytest.mark.unit
@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.usefixtures("no_database")
def test_each_command_refuses_a_persistent_target_before_connecting(
    command: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(_database_url: str) -> None:
        raise LoadTargetError("Refusing to load: HEAD is not on origin/main")

    monkeypatch.setattr(cli_main, "require_load_target", refused)

    result = CliRunner().invoke(cli_main.app, [*command, APPROVAL])

    assert result.exit_code == 1
    assert "not on origin/main" in result.output
