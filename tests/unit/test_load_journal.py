"""The progress journal of a page-committing load (DATABASE_AUDIT_2026-11-10, R-03)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nba_data.scraping import load_journal
from nba_data.scraping.load_journal import journal_path_for, open_load_journal


def _lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.unit
def test_a_completed_run_records_its_pages_and_outcome(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    with open_load_journal(
        command="backfill-stats", parameters={"limit": 2}, output=output
    ) as journal:
        journal.page_committed({"team": "BOS", "status": "loaded"})
        journal.page_committed({"team": "ATL", "status": "failed"})

    lines = _lines(journal.path)
    assert journal.path.parent == tmp_path
    assert [line["event"] for line in lines] == [
        "run_started",
        "page_committed",
        "page_committed",
        "run_finished",
    ]
    assert {line["run_id"] for line in lines} == {journal.run_id}
    assert lines[0]["command"] == "backfill-stats"
    assert lines[0]["parameters"] == {"limit": 2}
    assert [line["sequence"] for line in lines[1:3]] == [1, 2]
    assert lines[2]["entry"] == {"team": "ATL", "status": "failed"}
    assert lines[3]["status"] == "completed"
    assert lines[3]["pages_committed"] == 2
    assert not output.exists()  # the journal never stands in for the report


@pytest.mark.unit
def test_an_interrupted_run_keeps_the_pages_it_committed(tmp_path: Path) -> None:
    with (
        pytest.raises(KeyboardInterrupt),
        open_load_journal(command="c", parameters={}, output=tmp_path / "r.json") as journal,
    ):
        journal.page_committed({"page": 1})
        raise KeyboardInterrupt

    last = _lines(journal.path)[-1]
    assert last["status"] == "interrupted"
    assert last["pages_committed"] == 1


@pytest.mark.unit
def test_a_failed_run_records_the_error(tmp_path: Path) -> None:
    with (
        pytest.raises(RuntimeError),
        open_load_journal(command="c", parameters={}, output=tmp_path / "r.json") as journal,
    ):
        raise RuntimeError("commit failed")

    last = _lines(journal.path)[-1]
    assert last["status"] == "failed"
    assert last["error"] == "RuntimeError: commit failed"
    assert last["pages_committed"] == 0


@pytest.mark.unit
def test_a_rerun_with_the_same_output_gets_its_own_journal(tmp_path: Path) -> None:
    output = tmp_path / "r.json"
    started = datetime(2026, 11, 14, 18, 0, tzinfo=UTC)
    first = journal_path_for("c", output, started=started)
    second = journal_path_for("c", output, started=started.replace(second=1))

    assert first != second
    assert first.name == "r.json.20261114T180000000000Z.progress.jsonl"


@pytest.mark.unit
def test_an_existing_journal_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    taken = tmp_path / "taken.progress.jsonl"
    taken.write_text("earlier run\n", encoding="utf-8")
    monkeypatch.setattr(load_journal, "journal_path_for", lambda *_args, **_kwargs: taken)

    with (
        pytest.raises(FileExistsError),
        open_load_journal(command="c", parameters={}, output=None),
    ):
        pass  # pragma: no cover

    assert taken.read_text(encoding="utf-8") == "earlier run\n"


@pytest.mark.unit
def test_without_an_output_the_journal_goes_to_the_default_directory(tmp_path: Path) -> None:
    with open_load_journal(command="backfill-stats", parameters={}, output=None) as journal:
        pass

    assert journal.path.parent == load_journal.DEFAULT_JOURNAL_DIR
    assert journal.path.name.startswith("backfill-stats.")
