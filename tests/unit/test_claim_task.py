"""Tests for the atomic track-slot claim.

The worktrees are real: a throwaway repository in `tmp_path` with a second
worktree added through `git worktree add --orphan`, so the lock location and
worktree discovery run exactly as they do in the repository.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from scripts import claim_task
from scripts.claim_task import EXIT_BUSY, EXIT_CLAIMED, EXIT_REJECTED, LOCK_PATH, claim
from scripts.validate_tasks import IN_PROGRESS_STAGES, STAGES

SCRIPTS_DIR = Path(claim_task.__file__).resolve().parent

CARD = """---
id: {card_id}
title: A card
track: {track}
areas:
  - {area}
priority: 50
depends_on: {depends_on}
read: []
validation: []
critical_actions: []
---
{body}"""

PARKED_BODY = """
# Implementation notes

## Parked

- Branch: feature/{card_id}-a-card
- Waiting on: {waiting_on}
- Parked: 2026-09-13
- Reason: needs a dependency bump that belongs to a shared card.
"""

# Waits for a common start signal, then claims; run as `python -c`.
_RACER = """
import pathlib, sys, time
sys.path.insert(0, sys.argv[1])
import claim_task
ready, go = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
ready.write_text("ready", encoding="utf-8")
while not go.exists():
    time.sleep(0.001)
raise SystemExit(claim_task.main(sys.argv[4:]))
"""


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _prepare_root(root: Path, track: str | None) -> None:
    for stage in STAGES:
        (root / "tasks" / stage).mkdir(parents=True, exist_ok=True)
    if track is not None:
        (root / ".local").mkdir(exist_ok=True)
        (root / ".local" / "track").write_text(f"{track}\n", encoding="utf-8")


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    """A main worktree bound to `data` and a linked worktree bound to `app`."""
    data_root = tmp_path / "data-root"
    data_root.mkdir()
    _git("init", "--quiet", cwd=data_root)
    app_root = tmp_path / "app-root"
    _git("worktree", "add", "--orphan", "--quiet", str(app_root), cwd=data_root)
    _prepare_root(data_root, "data")
    _prepare_root(app_root, "app")
    return data_root, app_root


def _write(
    root: Path,
    stage: str,
    card_id: str,
    *,
    track: str,
    area: str = "testing",
    depends_on: str = "[]",
    body: str = "",
) -> Path:
    path = root / "tasks" / stage / f"{card_id}.md"
    path.write_text(
        CARD.format(card_id=card_id, track=track, area=area, depends_on=depends_on, body=body),
        encoding="utf-8",
    )
    return path


def _in_progress(*roots: Path) -> list[str]:
    return sorted(
        path.name
        for root in roots
        for stage in IN_PROGRESS_STAGES
        for path in (root / "tasks" / stage).glob("*.md")
    )


def _return_active_cards_to_backlog(*roots: Path) -> None:
    for root in roots:
        for path in (root / "tasks" / "active").glob("*.md"):
            path.replace(root / "tasks" / "backlog" / path.name)


# --- happy paths --------------------------------------------------------------


@pytest.mark.unit
def test_claim_moves_a_backlog_card_and_releases_the_lock(roots):
    data_root, _ = roots
    _write(data_root, "backlog", "F4E-001", track="data", area="scraping")

    result = claim("F4E-001", data_root)

    assert result.code == EXIT_CLAIMED, result.message
    assert result.message == "claimed: tasks/backlog/F4E-001.md -> tasks/active/F4E-001.md"
    assert (data_root / "tasks" / "active" / "F4E-001.md").exists()
    assert not (data_root / "tasks" / "backlog" / "F4E-001.md").exists()
    assert not (data_root / LOCK_PATH).exists()


@pytest.mark.unit
def test_one_data_card_and_one_app_card_run_in_parallel(roots):
    data_root, app_root = roots
    _write(data_root, "backlog", "F4E-001", track="data", area="scraping")
    _write(app_root, "backlog", "F6-001", track="app", area="api")

    assert claim("F4E-001", data_root).code == EXIT_CLAIMED
    result = claim("F6-001", app_root)

    assert result.code == EXIT_CLAIMED, result.message
    assert _in_progress(data_root, app_root) == ["F4E-001.md", "F6-001.md"]


@pytest.mark.unit
def test_the_linked_worktree_takes_the_lock_in_the_main_worktree(roots):
    data_root, app_root = roots
    _write(app_root, "backlog", "F6-001", track="app", area="api")
    seen: list[bool] = []

    result = claim(
        "F6-001",
        app_root,
        before_move=lambda: seen.append(
            (data_root / LOCK_PATH).exists() and not (app_root / LOCK_PATH).exists()
        ),
    )

    assert result.code == EXIT_CLAIMED, result.message
    assert seen == [True]


@pytest.mark.unit
def test_cli_claims_and_reports(roots, capsys):
    data_root, _ = roots
    _write(data_root, "backlog", "F4E-001", track="data", area="scraping")

    assert claim_task.main(["F4E-001", "--root", str(data_root)]) == EXIT_CLAIMED
    assert "claimed: tasks/backlog/F4E-001.md -> tasks/active/F4E-001.md" in capsys.readouterr().out


@pytest.mark.unit
def test_resume_claims_a_parked_card_whose_blocker_is_done(roots):
    _, app_root = roots
    _write(app_root, "done", "WF-001", track="shared", area="documentation")
    _write(
        app_root,
        "planning",
        "F6-001",
        track="app",
        area="api",
        depends_on="\n  - WF-001",
        body=PARKED_BODY.format(card_id="F6-001", waiting_on="WF-001"),
    )

    result = claim("F6-001", app_root, resume=True)

    assert result.code == EXIT_CLAIMED, result.message
    assert result.message == "claimed: tasks/planning/F6-001.md -> tasks/active/F6-001.md"


# --- exclusion ----------------------------------------------------------------


@pytest.mark.unit
def test_a_claim_holding_the_lock_makes_a_shared_claim_busy_then_rejected(roots):
    data_root, app_root = roots
    _write(data_root, "backlog", "F4E-001", track="data", area="scraping")
    _write(app_root, "backlog", "WF-001", track="shared", area="documentation")
    scanned = threading.Event()
    release = threading.Event()
    outcome: dict[str, claim_task.ClaimResult] = {}

    def hold_the_lock_after_scanning() -> None:
        scanned.set()
        if not release.wait(timeout=30):
            raise RuntimeError("the test never released the lock")

    def claim_data_card() -> None:
        outcome["data"] = claim("F4E-001", data_root, before_move=hold_the_lock_after_scanning)

    holder = threading.Thread(target=claim_data_card)
    holder.start()
    try:
        assert scanned.wait(timeout=30)
        busy = claim("WF-001", app_root, wait_seconds=0.2)
    finally:
        release.set()
        holder.join(timeout=30)

    assert busy.code == EXIT_BUSY, busy.message
    assert "card=F4E-001" in busy.message
    assert outcome["data"].code == EXIT_CLAIMED, outcome["data"].message

    retry = claim("WF-001", app_root, wait_seconds=1)

    assert retry.code == EXIT_REJECTED, retry.message
    assert "a shared card must be the only card" in retry.message
    assert _in_progress(data_root, app_root) == ["F4E-001.md"]
    assert not (data_root / LOCK_PATH).exists()


def _race(signals: Path, claims: list[tuple[Path, str]]) -> list[tuple[int, str]]:
    signals.mkdir()
    go = signals / "go"
    racers: list[tuple[Path, subprocess.Popen[str]]] = []
    for index, (root, card_id) in enumerate(claims):
        ready = signals / f"ready-{index}"
        command = [
            sys.executable,
            "-c",
            _RACER,
            str(SCRIPTS_DIR),
            str(ready),
            str(go),
            card_id,
            "--root",
            str(root),
            "--wait-seconds",
            "30",
        ]
        process = subprocess.Popen(
            command, cwd=signals, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        racers.append((ready, process))
    deadline = time.monotonic() + 60
    while not all(ready.exists() for ready, _ in racers):
        if time.monotonic() > deadline:
            for _, process in racers:
                process.kill()
            pytest.fail("racers never became ready")
        time.sleep(0.005)
    go.write_text("go", encoding="utf-8")
    results = []
    for _, process in racers:
        out, err = process.communicate(timeout=60)
        results.append((process.returncode, out + err))
    return results


@pytest.mark.unit
@pytest.mark.parametrize("variant", ["shared-and-app", "data-and-data"])
def test_real_concurrent_claims_leave_exactly_one_card_in_progress(roots, tmp_path, variant):
    data_root, app_root = roots
    if variant == "shared-and-app":
        _write(data_root, "backlog", "WF-001", track="shared", area="documentation")
        _write(app_root, "backlog", "F6-001", track="app", area="api")
        claims = [(data_root, "WF-001"), (app_root, "F6-001")]
    else:
        _write(data_root, "backlog", "F4E-001", track="data", area="scraping")
        _write(data_root, "backlog", "F4E-002", track="data", area="scraping")
        claims = [(data_root, "F4E-001"), (data_root, "F4E-002")]

    for iteration in range(20):
        results = _race(tmp_path / f"signals-{variant}-{iteration}", claims)

        assert sorted(code for code, _ in results) == [EXIT_CLAIMED, EXIT_REJECTED], results
        assert len(_in_progress(data_root, app_root)) == 1, results
        assert not (data_root / LOCK_PATH).exists()
        _return_active_cards_to_backlog(data_root, app_root)


# --- the lock -----------------------------------------------------------------


@pytest.mark.unit
def test_a_pre_existing_lock_reports_busy_and_is_left_untouched(roots):
    data_root, _ = roots
    card = _write(data_root, "backlog", "F4E-001", track="data", area="scraping")
    lock = data_root / LOCK_PATH
    content = b'{"pid": 4242, "worktree": "elsewhere", "card": "F4E-999", "acquired_at": "x"}'
    lock.write_bytes(content)

    result = claim("F4E-001", data_root, wait_seconds=0.2)

    assert result.code == EXIT_BUSY, result.message
    assert "pid=4242" in result.message
    assert "never deletes a lock it did not create" in result.message
    assert lock.read_bytes() == content
    assert card.exists()


@pytest.mark.unit
def test_the_lock_is_released_after_a_rejection(roots):
    data_root, _ = roots

    result = claim("F4E-404", data_root)

    assert result.code == EXIT_REJECTED
    assert "no card with id 'F4E-404'" in result.message
    assert not (data_root / LOCK_PATH).exists()


@pytest.mark.unit
def test_the_lock_is_released_when_the_claim_raises(roots):
    data_root, _ = roots
    card = _write(data_root, "backlog", "F4E-001", track="data", area="scraping")

    def explode() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        claim("F4E-001", data_root, before_move=explode)

    assert not (data_root / LOCK_PATH).exists()
    assert card.exists()


# --- rejections ---------------------------------------------------------------


@pytest.mark.unit
def test_claim_rejects_a_card_of_the_other_track(roots):
    _, app_root = roots
    card = _write(app_root, "backlog", "F4E-001", track="data", area="scraping")

    result = claim("F4E-001", app_root)

    assert result.code == EXIT_REJECTED
    assert "is a 'data' card and app-root is bound to 'app'" in result.message
    assert card.exists()


@pytest.mark.unit
def test_claim_rejects_an_unbound_worktree(roots):
    data_root, _ = roots
    (data_root / ".local" / "track").unlink()
    _write(data_root, "backlog", "F4E-001", track="data", area="scraping")

    result = claim("F4E-001", data_root)

    assert result.code == EXIT_REJECTED
    assert "is not bound to a track" in result.message


@pytest.mark.unit
def test_claim_rejects_two_worktrees_bound_to_the_same_track(roots):
    data_root, app_root = roots
    (app_root / ".local" / "track").write_text("data\n", encoding="utf-8")
    _write(data_root, "backlog", "F4E-001", track="data", area="scraping")

    result = claim("F4E-001", data_root)

    assert result.code == EXIT_REJECTED
    assert "track 'data' is bound to several worktrees" in result.message


@pytest.mark.unit
def test_claim_rejects_a_card_that_left_its_origin_folder(roots):
    data_root, _ = roots
    _write(data_root, "review", "F4E-001", track="data", area="scraping")

    result = claim("F4E-001", data_root)

    assert result.code == EXIT_REJECTED
    assert "F4E-001 is in tasks/review/, not tasks/backlog/" in result.message


@pytest.mark.unit
def test_claim_rejects_dependencies_that_are_not_done(roots):
    data_root, _ = roots
    _write(data_root, "backlog", "F4E-001", track="data", area="scraping")
    card = _write(
        data_root, "backlog", "F4E-002", track="data", area="scraping", depends_on="\n  - F4E-001"
    )

    result = claim("F4E-002", data_root)

    assert result.code == EXIT_REJECTED
    assert "dependency 'F4E-001' is in tasks/backlog/, not in tasks/done/" in result.message
    assert card.exists()


@pytest.mark.unit
def test_claim_rejects_areas_of_the_other_track(roots):
    _, app_root = roots
    _write(app_root, "backlog", "F6-001", track="app", area="database-schema")

    result = claim("F6-001", app_root)

    assert result.code == EXIT_REJECTED
    assert "area 'database-schema' belongs to track 'data'" in result.message


@pytest.mark.unit
def test_planning_to_active_needs_resume(roots):
    _, app_root = roots
    _write(app_root, "done", "WF-001", track="shared", area="documentation")
    card = _write(
        app_root,
        "planning",
        "F6-001",
        track="app",
        area="api",
        depends_on="\n  - WF-001",
        body=PARKED_BODY.format(card_id="F6-001", waiting_on="WF-001"),
    )

    result = claim("F6-001", app_root)

    assert result.code == EXIT_REJECTED
    assert "not tasks/backlog/; a parked card is claimed with --resume" in result.message
    assert card.exists()


@pytest.mark.unit
def test_resume_rejects_a_planning_card_that_was_never_parked(roots):
    _, app_root = roots
    card = _write(app_root, "planning", "F6-001", track="app", area="api")

    result = claim("F6-001", app_root, resume=True)

    assert result.code == EXIT_REJECTED
    assert "has no '## Parked' notes" in result.message
    assert card.exists()


@pytest.mark.unit
def test_resume_rejects_a_parked_card_whose_blocker_is_not_done(roots):
    _, app_root = roots
    _write(app_root, "backlog", "WF-001", track="shared", area="documentation")
    _write(
        app_root,
        "planning",
        "F6-001",
        track="app",
        area="api",
        depends_on="\n  - WF-001",
        body=PARKED_BODY.format(card_id="F6-001", waiting_on="WF-001"),
    )

    result = claim("F6-001", app_root, resume=True)

    assert result.code == EXIT_REJECTED
    assert "dependency 'WF-001' is in tasks/backlog/" in result.message
