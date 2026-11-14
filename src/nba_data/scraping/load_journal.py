"""A durable record of what a page-committing load has committed so far.

The stats backfills commit page by page (DATABASE_AUDIT_2026-11-10, R-03), but
their JSON report is written only when the run ends. A run that is interrupted,
or whose commit fails, keeps its committed pages and would otherwise leave no
evidence of which ones they are. The journal is that evidence.

It is JSON Lines, one object per line, each flushed and fsynced before the load
moves on:

- `run_started`: the run's id, command, parameters, process id and start time.
- `page_committed`: one per page, written only after its commit succeeded, with
  the page's own report entry. A crash between a commit and its line loses at
  most that one line; the page is still in the database and a rerun upserts it.
- `run_finished`: `completed`, `interrupted` or `failed` (with the error). A
  journal without it belongs to a process that was killed.

The journal is evidence for an operator, never a report: no validator accepts
it, and a completed run still writes its report as before.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

JOURNAL_SUFFIX = ".progress.jsonl"
DEFAULT_JOURNAL_DIR = Path("logs/load-progress")

#: What a producer calls with a page's report entry once the page is committed.
PageCommittedCallback = Callable[[Mapping[str, object]], None]


class LoadJournal:
    """Append-only progress lines for one run. Use `open_load_journal`."""

    def __init__(self, handle: IO[str], *, path: Path, run_id: str) -> None:
        self._handle = handle
        self.path = path
        self.run_id = run_id
        self.pages_committed = 0

    def page_committed(self, entry: Mapping[str, object]) -> None:
        """Record a page whose commit has already succeeded."""
        self.pages_committed += 1
        self._write(
            {"event": "page_committed", "sequence": self.pages_committed, "entry": dict(entry)}
        )

    def _write(self, record: Mapping[str, object]) -> None:
        line = {"run_id": self.run_id, "at": _now(), **record}
        self._handle.write(json.dumps(line, default=str, sort_keys=True) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())


def journal_path_for(command: str, output: Path | None, *, started: datetime) -> Path:
    """Beside the report when there is one, else under `logs/load-progress/`.

    The name carries the start time, so a rerun with the same `--output` never
    overwrites the journal of the run it is recovering from.
    """
    stamp = started.strftime("%Y%m%dT%H%M%S%fZ")
    if output is not None:
        return output.with_name(f"{output.name}.{stamp}{JOURNAL_SUFFIX}")
    return DEFAULT_JOURNAL_DIR / f"{command}.{stamp}{JOURNAL_SUFFIX}"


@contextmanager
def open_load_journal(
    *, command: str, parameters: Mapping[str, object], output: Path | None
) -> Iterator[LoadJournal]:
    """Start a journal, and close it with the run's outcome however the run ends."""
    started = datetime.now(UTC)
    path = journal_path_for(command, output, started=started)
    path.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    # "x": never overwrite an existing journal, whatever its name collides with.
    with path.open("x", encoding="utf-8") as handle:
        journal = LoadJournal(handle, path=path, run_id=run_id)
        journal._write(
            {
                "event": "run_started",
                "command": command,
                "parameters": dict(parameters),
                "pid": os.getpid(),
            }
        )
        try:
            yield journal
        except KeyboardInterrupt:
            _finish(journal, "interrupted", error="KeyboardInterrupt")
            raise
        except BaseException as exc:
            _finish(journal, "failed", error=f"{type(exc).__name__}: {exc}")
            raise
        _finish(journal, "completed")


def _finish(journal: LoadJournal, status: str, *, error: str | None = None) -> None:
    # A journal that cannot be written must not hide the run's own error.
    with suppress(OSError):
        _write_finish(journal, status, error=error)


def _write_finish(journal: LoadJournal, status: str, *, error: str | None) -> None:
    record: dict[str, object] = {
        "event": "run_finished",
        "status": status,
        "pages_committed": journal.pages_committed,
    }
    if error is not None:
        record["error"] = error
    journal._write(record)


def _now() -> str:
    return datetime.now(UTC).isoformat()
