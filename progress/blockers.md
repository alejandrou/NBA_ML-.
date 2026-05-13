# Blockers

No active blockers.

## Resolved

- Phase 1 Git tracking blocker: `.gitignore` previously ignored required docs,
  task/progress memory, specs, harness scripts, and Codex prompts. The ignore
  policy was narrowed and harness init now fails if required files are ignored
  or untracked.
