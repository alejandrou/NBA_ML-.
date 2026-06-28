# Prompt Templates

## Template 1 - Generic Implementation Task

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<ID>_CODEX_CONTEXT.md

Owner approval:
- Mark <PREVIOUS_TASK_ID> as done if explicitly approved.

Task:
Implement <TASK_ID> according to:
- specs/features/<TASK_SPEC>.md

Scope:
- <short scope>
- No <explicit exclusions>

Expected files:
- <file 1>
- <file 2>
- <file 3>

Final state:
- <PREVIOUS_TASK_ID>: done
- <TASK_ID>: needs_review
- next tasks: pending

Validation:
Follow docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md.

Commit and push:
<yes/no>
<commit command if yes>
```

## Template 2 - Start New Phase Branch

```text
Actua como agente documentador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/CODEX_USAGE_OPTIMIZATION.md

Task:
Start context setup for the new phase:

<PHASE_ID> - <PHASE_NAME>

Create:
- docs/ai/PHASE_<ID>_CODEX_CONTEXT.md

Use:
- docs/roadmap/CURRENT_PHASE.md
- tasks/feature-list.json
- docs/roadmap/TASKS.md
- progress/current.md
- progress/review.md
- specs/phases/<PHASE_SPEC>.md
- relevant architecture docs

Do not implement code.
Do not change DB.
Do not start feature work.

Final state:
- phase context exists and is concise.
```

## Template 3 - Owner-Approved Closure and Next Task

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<ID>_CODEX_CONTEXT.md

Owner approval:
I, as project owner, explicitly approve closing <PREVIOUS_TASK_ID> as done.

Task:
Implement <TASK_ID> according to:
- specs/features/<TASK_SPEC>.md

Final state:
- <PREVIOUS_TASK_ID>: done
- <TASK_ID>: needs_review
- later tasks: pending

Commit and push after validation.
```

## Template 4 - Review-Only Task

```text
Actua como agente revisor.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<ID>_CODEX_CONTEXT.md

Task:
Review <TASK_ID> implementation.

Check:
- scope
- tests
- docs
- task state
- validation results
- no out-of-scope changes

Do not implement unless a small fix is required.
Do not commit unless explicitly requested.

Output:
- pass/fail
- issues
- recommended next step
```

## Template 5 - Compact Task Prompt

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<ID>_CODEX_CONTEXT.md

Implement <TASK_ID> using:
- specs/features/<TASK_SPEC>.md

Read additional files only if needed.

Final state:
- <TASK_ID>: needs_review

Validate.
Short final response.
```
