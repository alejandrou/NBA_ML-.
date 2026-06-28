# Codex Usage Optimization

## Main Principle

The repository should be the memory, not the prompt.

## Practical Rules

1. Use one prompt per task.
2. Do not paste long historical context.
3. Reference repository files instead of copying their contents.
4. Use one compact phase context file per phase.
5. Use the global execution protocol for repeated workflow rules.
6. Give a short list of relevant files.
7. Read additional files only if needed.
8. Ask for a short final response.
9. Avoid broad repository scans unless needed.
10. Use `rg` or `git grep` before opening large files.
11. Keep task specs as the contract for implementation.
12. Keep task state in `tasks/feature-list.json`, not in prompts.
13. Keep phase state in `docs/roadmap/CURRENT_PHASE.md` and phase context
    docs.
14. Keep progress in `progress/current.md` and `progress/review.md`.
15. Use one commit per task or phase unit when a commit is requested.
16. Open a new working session when moving to a major new phase.
17. Create a new phase context doc at the start of each phase branch.
18. Do not duplicate full specs inside context docs.

## What Belongs Where

| Item | Location | Frequency |
|---|---|---|
| Global workflow rules | `docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md` | Rarely changes |
| Usage strategy | `docs/ai/CODEX_USAGE_OPTIMIZATION.md` | Rarely changes |
| Phase context | `docs/ai/PHASE_<ID>_CODEX_CONTEXT.md` | Once per phase, update as needed |
| Task contract | `specs/features/<TASK>.md` | Per task |
| Task state | `tasks/feature-list.json` | Per task update |
| Current phase | `docs/roadmap/CURRENT_PHASE.md` | Per phase |
| Progress | `progress/current.md` / `progress/review.md` | Per task |
| Commit message | Prompt or generated per task | Per task |

## What Should Not Be Repeated In Prompts

- `Lee AGENTS.md`
- Global workflow rules
- No scraping unless allowed
- No push unless requested
- Use `rg`
- Final response short
- Do not add temp files
- Validation command list
- Generic commit rules

These belong in the global execution protocol instead.

## What Should Be Adapted Per Phase

- Phase context file
- Branch name
- In scope and out of scope
- Phase gate
- Architecture decisions
- Relevant key files
- Extra validation commands

## What Should Be Adapted Per Task

- Task id
- Previous task owner approval if applicable
- Current task spec
- Expected final state
- Expected files
- Commit message
- Whether push is allowed
