"""Validate the repository's pointer-based task-card workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKS, SKILLS = ROOT / "tasks", ROOT / ".agents" / "skills"
ROADMAP = ROOT / "docs" / "roadmap" / "ROADMAP.md"
TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-[0-9]{3}$")
VALID_STATUSES = {"planned", "ready", "in_progress", "review", "blocked", "done", "cancelled"}
VALID_MODES = {"plan", "implement", "review"}
VALID_TYPES = {"api", "data-quality", "database", "docs", "maintenance", "migration", "scraping"}
LEGACY_NAMES = {"alembic", "api-endpoint", "clean-code", "codex-review", "database-migration", "feature-engineering", "frontend-page"}
LIST_FIELDS = {"skills", "must_read", "allowed_paths", "forbidden_paths", "validation"}


@dataclass
class Result:
    errors: list[str]
    warnings: list[str]

    def error(self, message: str) -> None:
        self.errors.append(f"ERROR: {message}")

    def warning(self, message: str) -> None:
        self.warnings.append(f"WARNING: {message}")


def split_frontmatter(path: Path, result: Result) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        result.error(f"{path.relative_to(ROOT)}: missing opening frontmatter delimiter")
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        result.error(f"{path.relative_to(ROOT)}: missing closing frontmatter delimiter")
        return None
    return text[4:end]


def value(raw: str) -> object:
    raw = raw.strip()
    if raw in {"", "null"}:
        return ""
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [] if not inner else [part.strip().strip('"\'') for part in inner.split(",")]
    return raw.strip('"\'')


def parse_frontmatter(path: Path, result: Result) -> dict[str, object] | None:
    frontmatter = split_frontmatter(path, result)
    if frontmatter is None:
        return None
    data: dict[str, object] = {}
    current_list: str | None = None
    for number, line in enumerate(frontmatter.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_list is None:
                result.error(f"{path.relative_to(ROOT)}:{number}: list item has no key")
                continue
            data.setdefault(current_list, [])
            assert isinstance(data[current_list], list)
            data[current_list].append(line[4:].strip().strip('"\''))
            continue
        if ":" not in line or line.startswith(" "):
            result.error(f"{path.relative_to(ROOT)}:{number}: unsupported YAML syntax")
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        if key in data:
            result.error(f"{path.relative_to(ROOT)}:{number}: duplicate field {key!r}")
        data[key] = [] if raw.strip() == "" and key in LIST_FIELDS else value(raw)
        current_list = key if raw.strip() == "" else None
    return data


def as_list(card: dict[str, object], key: str, path: Path, result: Result) -> list[str]:
    item = card.get(key)
    if not isinstance(item, list):
        result.error(f"{path.relative_to(ROOT)}: {key} must be a list")
        return []
    return [str(part) for part in item]


def roadmap_phases(result: Result) -> dict[str, str]:
    if not ROADMAP.is_file():
        result.error("docs/roadmap/ROADMAP.md is missing")
        return {}
    phases = {}
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*([a-z0-9-]+)\s*\|\s*(planned|active|blocked|done)\s*\|", line)
        if match:
            phases[match.group(1)] = match.group(2)
    if not phases:
        result.error("docs/roadmap/ROADMAP.md: no phase-status table found")
    return phases


def validate() -> Result:
    result = Result([], [])
    pointer = TASKS / "CURRENT.md"
    if not pointer.is_file():
        result.error("tasks/CURRENT.md is missing")
        return result
    pointer_data = parse_frontmatter(pointer, result)
    if pointer_data is None:
        return result
    if set(pointer_data) != {"task"} or not isinstance(pointer_data.get("task"), str):
        result.error("tasks/CURRENT.md: frontmatter must contain only a string task field")
        return result
    current_raw = str(pointer_data["task"])
    if Path(current_raw).is_absolute() or ".." in Path(current_raw).parts:
        result.error("tasks/CURRENT.md: task must be a repository-relative path")
        return result
    current = ROOT / current_raw
    if not current.is_file():
        result.error(f"tasks/CURRENT.md: target does not exist: {current_raw}")

    phases = roadmap_phases(result)
    for retired in (ROOT / "docs" / "ai", ROOT / "progress", TASKS / "feature-list.json"):
        if retired.exists():
            result.error(f"retired workflow path still exists: {retired.relative_to(ROOT)}")
    cards: list[tuple[Path, dict[str, object]]] = []
    ids: dict[str, Path] = {}
    required = {"task_id", "title", "phase", "task_type", "status", "mode", "skills", "must_read", "allowed_paths", "forbidden_paths", "validation", "requires_owner_approval", "owner_approved", "approval_scope", "next_task"}
    for path in sorted(TASKS.rglob("*.md")):
        if path.name in {"CURRENT.md", "TEMPLATE.md"}:
            continue
        card = parse_frontmatter(path, result)
        if card is None:
            continue
        cards.append((path, card))
        missing = required - set(card)
        if missing:
            result.error(f"{path.relative_to(ROOT)}: missing fields: {', '.join(sorted(missing))}")
        task_id = card.get("task_id")
        if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
            result.error(f"{path.relative_to(ROOT)}: invalid task_id {task_id!r}")
        elif task_id in ids:
            result.error(f"duplicate task_id {task_id}: {ids[task_id].relative_to(ROOT)} and {path.relative_to(ROOT)}")
        else:
            ids[task_id] = path
        if card.get("status") not in VALID_STATUSES:
            result.error(f"{path.relative_to(ROOT)}: invalid status {card.get('status')!r}")
        if card.get("mode") not in VALID_MODES:
            result.error(f"{path.relative_to(ROOT)}: invalid mode {card.get('mode')!r}")
        if card.get("task_type") not in VALID_TYPES:
            result.error(f"{path.relative_to(ROOT)}: invalid task_type {card.get('task_type')!r}")
        for skill in as_list(card, "skills", path, result):
            if skill in LEGACY_NAMES:
                result.error(f"{path.relative_to(ROOT)}: obsolete skill {skill!r}")
            if not (SKILLS / skill / "SKILL.md").is_file():
                result.error(f"{path.relative_to(ROOT)}: declared skill {skill!r} has no SKILL.md")
        for source in as_list(card, "must_read", path, result):
            if Path(source).is_absolute() or not (ROOT / source).is_file():
                result.error(f"{path.relative_to(ROOT)}: must_read file is missing: {source}")
        allowed, forbidden = as_list(card, "allowed_paths", path, result), as_list(card, "forbidden_paths", path, result)
        for raw in allowed + forbidden:
            if Path(raw).is_absolute():
                result.error(f"{path.relative_to(ROOT)}: path must be relative: {raw}")
        for allowed_path in allowed:
            for forbidden_path in forbidden:
                if allowed_path == forbidden_path or allowed_path.startswith(forbidden_path.rstrip("/") + "/"):
                    result.error(f"{path.relative_to(ROOT)}: allowed path {allowed_path} conflicts with forbidden path {forbidden_path}")
        next_task = card.get("next_task")
        if next_task and (not isinstance(next_task, str) or not (ROOT / next_task).is_file()):
            result.error(f"{path.relative_to(ROOT)}: next_task does not exist: {next_task}")
        if card.get("requires_owner_approval") is True and card.get("owner_approved") is not True and card.get("status") == "in_progress":
            result.error(f"{path.relative_to(ROOT)}: approval is required before in_progress")
        phase_status = phases.get(str(card.get("phase")))
        if phase_status is None:
            result.error(f"{path.relative_to(ROOT)}: unknown phase {card.get('phase')!r}")
        elif card.get("status") in {"in_progress", "review", "blocked"} and phase_status != "active":
            result.error(f"{path.relative_to(ROOT)}: {card.get('status')} task requires an active phase")
        elif card.get("status") == "ready" and phase_status == "done":
            result.error(f"{path.relative_to(ROOT)}: ready task cannot belong to a done phase")
        if len(path.read_text(encoding="utf-8").splitlines()) > 250:
            result.warning(f"{path.relative_to(ROOT)} has more than 250 lines; extract durable context")
        for key, limit in (("must_read", 10), ("skills", 5), ("allowed_paths", 12)):
            if len(as_list(card, key, path, result)) > limit:
                result.warning(f"{path.relative_to(ROOT)}: {key} exceeds recommended limit of {limit}")
    in_progress = [path for path, card in cards if card.get("status") == "in_progress"]
    if len(in_progress) > 1:
        result.error("more than one task is in_progress: " + ", ".join(str(path.relative_to(ROOT)) for path in in_progress))
    if len(in_progress) == 1 and in_progress[0] != current:
        result.error(f"{in_progress[0].relative_to(ROOT)} is in_progress but is not tasks/CURRENT.md target")
    if current.is_file():
        active = next((card for path, card in cards if path == current), None)
        if active is not None and active.get("status") not in {"ready", "in_progress", "review", "blocked"}:
            result.error(f"tasks/CURRENT.md points to task with invalid active status {active.get('status')!r}")
    return result


def main() -> int:
    result = validate()
    for message in result.warnings + result.errors:
        print(message)
    if result.errors:
        print(f"Workflow validation failed with {len(result.errors)} error(s).")
        return 1
    print("Workflow validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
