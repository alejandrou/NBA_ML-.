"""Claim a track slot and move one card into `tasks/active/`, atomically.

Checking the slots and occupying one must be a single operation across every
worktree of the repository; otherwise two sessions can both see a free slot and
both start. This script is that operation:

    uv run python scripts/claim_task.py <TASK-ID>            # backlog/ -> active/
    uv run python scripts/claim_task.py --resume <TASK-ID>   # planning/ -> active/, parked cards

Inside one exclusive lock (`<main worktree>/.local/task-slot.lock`, created with
O_CREAT | O_EXCL) it lists the worktrees, reads `active/` and `review/` of each,
checks this worktree's `.local/track` against the card, checks the card is still
in its origin folder with its dependencies done, applies the slot rules with the
candidate added, and moves the card with `os.replace`. The folders remain the
only state: nothing is reserved anywhere else.

Only entries into `active/` need the lock. Moves out of `active/` or `review/`
only free a slot, and a concurrent claim that still sees the card rejects, which
is the conservative outcome.

Exit codes: 0 claimed; 1 rejected, nothing moved; 3 busy, the lock stayed held
for the whole wait and nothing moved. It never deletes a lock it did not create:
an orphaned lock is reported with its holder, and only the owner removes it.
Standard library only; the one Git command it runs is the read-only
`git worktree list --porcelain`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts import validate_tasks as tasks
except ImportError:  # run as `python scripts/claim_task.py`
    import validate_tasks as tasks  # type: ignore[no-redef]

EXIT_CLAIMED = 0
EXIT_REJECTED = 1
EXIT_BUSY = 3
LOCK_PATH = Path(".local") / "task-slot.lock"
DEFAULT_WAIT_SECONDS = 10.0
POLL_SECONDS = 0.05
_UNLOCK_ATTEMPTS = 40


class Busy(Exception):
    """The slot lock stayed held for the whole wait."""


class Rejected(Exception):
    """The claim is not allowed; nothing was moved."""


@dataclass(frozen=True)
class ClaimResult:
    code: int
    message: str


def _describe_holder(path: Path) -> str:
    try:
        holder = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "was released just now; retry"
    except (OSError, ValueError):
        return "is held (holder details unreadable)"
    if not isinstance(holder, dict):
        return "is held (holder details unreadable)"
    details = ", ".join(
        f"{key}={holder.get(key, '?')}" for key in ("pid", "worktree", "card", "acquired_at")
    )
    return f"is held by {details}"


@contextmanager
def slot_lock(
    path: Path,
    *,
    card_id: str,
    root: Path,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
    poll_seconds: float = POLL_SECONDS,
) -> Iterator[None]:
    """Hold the exclusive slot lock for the body of the `with` block.

    Waits up to `wait_seconds`, then raises `Busy`. Removes only the lock it
    created, on success, rejection, or exception alike.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, PermissionError):
            # Windows reports a lock that is being deleted as PermissionError.
            if time.monotonic() >= deadline:
                raise Busy(
                    f"{path} {_describe_holder(path)}; waited {wait_seconds:g}s. If no claim "
                    "is running the lock is orphaned: check the holder, then the owner "
                    "removes it. This script never deletes a lock it did not create."
                ) from None
            time.sleep(poll_seconds)
            continue
        break
    try:
        holder = {
            "pid": os.getpid(),
            "worktree": str(root),
            "card": card_id,
            "acquired_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(holder, handle)
        yield
    finally:
        _unlink_own_lock(path)


def _unlink_own_lock(path: Path) -> None:
    # A waiter reading the holder details briefly keeps the file open, which
    # makes deletion fail on Windows; retry for about two seconds.
    for attempt in range(_UNLOCK_ATTEMPTS):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == _UNLOCK_ATTEMPTS - 1:
                raise
            time.sleep(POLL_SECONDS)


def _existing_unique(roots: list[Path]) -> list[Path]:
    unique: list[Path] = []
    for root in roots:
        if root.is_dir() and not any(os.path.samefile(root, seen) for seen in unique):
            unique.append(root)
    return unique


def _claim_locked(
    card_id: str,
    root: Path,
    *,
    resume: bool,
    before_move: Callable[[], None] | None,
) -> str:
    origin = "planning" if resume else "backlog"

    worktrees: list[tasks.Worktree] = []
    for worktree_root in _existing_unique([root, *tasks.list_worktrees(root)]):
        worktree, load_errors = tasks.load_worktree(worktree_root)
        if load_errors:
            raise Rejected("cannot read in-progress cards: " + "; ".join(load_errors))
        worktrees.append(worktree)
    binding_errors = tasks.check_worktree_bindings(worktrees)
    if binding_errors:
        raise Rejected("; ".join(binding_errors))
    binding = tasks.read_track_binding(root)
    if binding is None:
        raise Rejected(
            f"{root} is not bound to a track; write 'data' or 'app' to "
            f"{tasks.TRACK_BINDING_PATH.as_posix()}"
        )

    cards, parse_errors = tasks.load_cards(root / "tasks")
    matches = [card for card in cards if card.card_id == card_id]
    if not matches:
        raise Rejected(f"no card with id {card_id!r} in {root / 'tasks'}")
    source = next((card for card in matches if card.stage == origin), None)
    if source is None:
        found = ", ".join(f"tasks/{card.stage}/" for card in matches)
        hint = (
            "; a parked card is claimed with --resume"
            if not resume and any(card.stage == "planning" for card in matches)
            else ""
        )
        raise Rejected(f"{card_id} is in {found}, not tasks/{origin}/{hint}")
    own_parse_errors = [error for error in parse_errors if error.startswith(source.label)]
    if own_parse_errors:
        raise Rejected("; ".join(own_parse_errors))
    destination = root / "tasks" / "active" / source.path.name
    if destination.exists():
        raise Rejected(f"{destination} already exists")

    candidate = replace(source, stage="active", origin=f"{root.name} (candidate)")
    problems = [
        *tasks.check_track_field([candidate]),
        *tasks.check_areas_match_track([candidate]),
        *tasks.check_id_family_matches_track([candidate]),
        *tasks.check_backlog_decisions_resolved([replace(source, stage="backlog")]),
    ]
    if source.track in tasks.BOUND_TRACKS and source.track != binding:
        problems.append(
            f"{card_id} is a {source.track!r} card and {root.name} is bound to {binding!r}"
        )
    stage_of = {card.card_id: card.stage for card in cards if card.card_id}
    problems.extend(
        f"{card_id}: dependency {dep!r} is "
        f"{'in tasks/' + stage_of[dep] + '/' if dep in stage_of else 'not found'}, "
        "not in tasks/done/"
        for dep in source.list_field("depends_on")
        if stage_of.get(dep) != "done"
    )
    if resume:
        section = tasks.parked_section(source)
        if section is None:
            problems.append(f"{card_id} has no '## Parked' notes; only a parked card resumes")
        elif "Resumed" in tasks.parked_fields(section):
            problems.append(f"{card_id} already records '- Resumed:'")
        else:
            problems.extend(
                error
                for error in tasks.check_parked_cards(cards)
                if error.startswith(source.label)
            )
    in_progress = [card for worktree in worktrees for card in worktree.cards]
    problems.extend(tasks.check_track_slots([*in_progress, candidate]))
    if problems:
        raise Rejected("; ".join(problems))

    if before_move is not None:
        before_move()
    os.replace(source.path, destination)
    return f"tasks/{origin}/{source.path.name} -> tasks/active/{source.path.name}"


def claim(
    card_id: str,
    root: Path,
    *,
    resume: bool = False,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
    poll_seconds: float = POLL_SECONDS,
    before_move: Callable[[], None] | None = None,
) -> ClaimResult:
    """Claim `card_id` for the worktree at `root`.

    `before_move` runs inside the lock after every check and before the move;
    tests use it to hold the lock at the most contended point.
    """
    root = root.resolve()
    try:
        worktree_roots = tasks.list_worktrees(root)
    except tasks.WorktreeError as exc:
        return ClaimResult(EXIT_REJECTED, f"rejected: {exc}")
    if not worktree_roots:
        return ClaimResult(EXIT_REJECTED, f"rejected: no Git worktree found for {root}")
    try:
        with slot_lock(
            worktree_roots[0] / LOCK_PATH,
            card_id=card_id,
            root=root,
            wait_seconds=wait_seconds,
            poll_seconds=poll_seconds,
        ):
            moved = _claim_locked(card_id, root, resume=resume, before_move=before_move)
    except Busy as exc:
        return ClaimResult(EXIT_BUSY, f"busy: {exc}")
    except (Rejected, tasks.WorktreeError) as exc:
        return ClaimResult(EXIT_REJECTED, f"rejected: {exc}")
    return ClaimResult(EXIT_CLAIMED, f"claimed: {moved}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Atomically claim a track slot and move a card into tasks/active/."
    )
    parser.add_argument("card_id", metavar="TASK-ID")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Claim a parked card from tasks/planning/ instead of tasks/backlog/.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Worktree whose card is claimed (default: the worktree holding this script).",
    )
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=DEFAULT_WAIT_SECONDS,
        help=f"How long to wait for the lock before reporting busy (default: {DEFAULT_WAIT_SECONDS:g}).",
    )
    args = parser.parse_args(argv)
    result = claim(args.card_id, args.root, resume=args.resume, wait_seconds=args.wait_seconds)
    print(result.message)
    return result.code


if __name__ == "__main__":
    raise SystemExit(main())
