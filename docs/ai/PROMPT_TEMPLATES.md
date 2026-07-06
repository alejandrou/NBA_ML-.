# Prompt Templates

## Template 1 - Ultrashort Implementation

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md

Task:
Implement <TASK_ID> according to:
- specs/features/<TASK_SPEC>.md

Scope:
- <short scope>
- No out-of-scope work

Expected files:
- <file 1>
- <file 2>

Final state:
- <TASK_ID>: needs_review

Validation:
Follow docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md.

Commit and push:
<yes/no>
```

## Template 2 - Documentation Only

```text
Actua como agente documentador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/CODEX_USAGE_OPTIMIZATION.md

Task:
Update docs only:
- <files>

Do not change code, DB, or task state.

Final state:
- documentation updated
```

## Template 3 - Review Only

```text
Actua como agente revisor.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md

Task:
Review <TASK_ID> implementation.

Check:
- scope
- tests
- docs
- validation
- task state

Do not implement unless a small fix is required.
Do not commit unless explicitly requested.

Output:
- pass/fail
- issues
- next step
```

## Template 4 - Fix After Review

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md

Task:
Fix review issues for <TASK_ID>.

Use:
- review notes
- specs/features/<TASK_SPEC>.md

Do not expand scope.

Final state:
- <TASK_ID>: needs_review
```

## Template 5 - Task Card Prompt

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md
- docs/ai/tasks/<TASK_CARD>.md

Implement <TASK_ID> using the task card and the exact feature spec.

Read additional files only if needed.

Final state:
- <TASK_ID>: needs_review

Validate.
Short final response.
```

## Template 6 - New Phase

```text
Actua como agente documentador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/CODEX_USAGE_OPTIMIZATION.md

Set up the new phase context for:
- <PHASE_ID> - <PHASE_NAME>

Create:
- docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md

Use only the phase spec, current phase, task list, and progress docs.
Do not implement code, DB changes, or feature work.
```

## Template 7 - Commit And Push

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md

Implement <TASK_ID> from:
- specs/features/<TASK_SPEC>.md

After validation:
- commit with <COMMIT_MESSAGE>
- push to the current branch
```

## Template 8 - No Commit Or Push

```text
Actua como agente implementador.

Sigue:
- docs/ai/CODEX_PHASE_EXECUTION_PROTOCOL.md
- docs/ai/PHASE_<CURRENT_PHASE_SHORT_ID>_CODEX_CONTEXT.md

Implement <TASK_ID> from:
- specs/features/<TASK_SPEC>.md

Do not commit or push.
Return validation status only.
```
