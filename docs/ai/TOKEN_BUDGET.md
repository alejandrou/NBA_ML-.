# Context and token budget

Normal startup is limited to:

1. `AGENTS.md`;
2. `docs/ai/CURRENT_TASK.md`;
3. its task card;
4. declared skills;
5. `must_read` files.

Use `rg` before opening files, never read directories wholesale, and do not
load `progress/history.md`, `progress/review.md`, or learning logs by default.
Load skill references only when the task needs them. Avoid duplicating the
same architecture in the current-task pointer, task card, skills, and specs.
Justify additional reads for large tasks in the task card or progress note.
