"""Refuse a load into a persistent database from code that is not on `origin/main`.

AGENTS.md allows a load into `nba` only from merged `origin/main`. A database
whose name does not mark it as disposable counts as persistent, and anything
that stops the checkout from being verified refuses the load.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence

from sqlalchemy.engine import make_url

DISPOSABLE_DATABASE_PREFIX = "nba_test"
_CODE_PATHS = ("src", "alembic")

GitRunner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


class LoadTargetError(Exception):
    """The configured database may not be loaded from this checkout."""


def _run_git(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], capture_output=True, text=True, check=False)


def require_load_target(database_url: str, *, git: GitRunner = _run_git) -> None:
    """Pass a disposable database; otherwise require a clean checkout of merged code."""

    database = make_url(database_url).database or ""
    if database.startswith(DISPOSABLE_DATABASE_PREFIX):
        return
    target = f"persistent database {database!r}"
    try:
        merged = git(["merge-base", "--is-ancestor", "HEAD", "origin/main"])
        status = git(["status", "--porcelain", "--", *_CODE_PATHS])
    except OSError as exc:
        msg = f"Refusing to load {target}: cannot inspect the checkout ({exc})"
        raise LoadTargetError(msg) from exc
    if merged.returncode != 0:
        msg = f"Refusing to load {target}: HEAD is not on origin/main"
        raise LoadTargetError(msg)
    if status.returncode != 0 or status.stdout.strip():
        msg = f"Refusing to load {target}: the checkout has uncommitted code changes"
        raise LoadTargetError(msg)


__all__ = ["DISPOSABLE_DATABASE_PREFIX", "GitRunner", "LoadTargetError", "require_load_target"]
