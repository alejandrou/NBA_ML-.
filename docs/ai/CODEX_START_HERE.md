# Codex start here

`AGENTS.md` is the repository router. Every task starts at
`docs/ai/CURRENT_TASK.md`, then opens only the referenced task card. The card
declares the mode, skills, required context, allowed paths, and validation.

Use focused `rg` searches for extra context. Keep historical progress and large
roadmap files out of the startup path unless the task requires them.

The JSON task list remains available for project tooling and historical state;
it is not the active Codex task interface.
