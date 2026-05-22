# Current Work

Status: phase_4a_in_progress

## Active Task

No task is approved, in progress, or needs review.

## Current Phase

- Phase ID: `phase-4a-legacy-scraper-consolidation`
- Phase status: `in_progress`
- Completed Phase 4A tasks:
  - `F4A-000` - Add legacy parity and acquisition smoke-test strategy.
- Pending Phase 4A tasks:
  - `F4A-001` - Consolidate legacy scrapers behind cache-first providers.
  - `F4A-002` - Design bounded offline cached HTML processing.
- Phase 4 SQLAlchemy migration is not active; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.

## Goal

Phase 4A is active as a legacy scraper consolidation gate before any controlled
raw HTML backfill or Phase 4 SQLAlchemy migration work. `F4A-000` is closed as
the reviewed strategy gate for offline parity and one-page manual live
acquisition smoke testing.

## Next Safe Action

Ask for explicit owner approval before promoting or implementing `F4A-001`,
starting `F4A-002`, activating Phase 4 SQLAlchemy migration, running live
scraping, contacting Basketball Reference, running controlled backfill, writing
DB data, applying migrations, deleting legacy/Peewee code, creating a PR, or
implementing API/frontend/OVR work.

## Latest Review Result

- `F4A-000` acceptance criteria are covered by
  `specs/features/F4A-000-legacy-parity-and-acquisition-smoke-test-strategy.md`,
  ADR 0016, ADR 0015, and ADR 0004.
- The strategy defines offline legacy-vs-new parser parity from frozen or
  fixture-copied cached HTML.
- The parity scope compares legacy roster, totals, and advanced outputs against
  the future consolidated parser/adapter.
- Unit tests and CI remain fully offline.
- The manual live smoke test is separate, owner-approved per exact URL,
  cache-first, at most one live request on cache miss, shape-only, and routed
  through `BasketballReferenceClient` and `HtmlCache`.
- The rate-limit policy remains 10 requests/minute by default and never above
  20 requests/minute.
- HTTP 429 stops safely through the central client behavior.
- No DB writes, full historical scraping, live concurrency, controlled backfill,
  migrations, API/frontend/OVR, or legacy/Peewee deletion were introduced.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh`: passed,
  43 passed and 3 Peewee deprecation warnings.

## Notes

No live scraping was run. No Basketball Reference contact occurred. No DB
writes, DB migrations, controlled backfill, legacy/Peewee deletion,
API/frontend/OVR, commit, push, or PR occurred.

The local branch is `feature/fase-4a-legacy-scraper-consolidation`, created
from `b2c9960cc969bfc4c718cffd6534e6a46245704e`.

The pre-existing local modification in
`specs/phases/phase-2-scraper-cache-integration.md` remains outside this work
and was not edited or reverted.

## Continuation Prompt

Use this prompt when continuing in a new Codex window:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Current branch expected: feature/fase-4a-legacy-scraper-consolidation
Current HEAD expected: b2c9960cc969bfc4c718cffd6534e6a46245704e

Actua como owner/leader + implementer/reviewer del repo.

Primero sigue el startup protocol:
1. Lee AGENTS.md.
2. Ejecuta "C:\Program Files\Git\bin\bash.exe" scripts/harness/init.sh
3. Lee docs/ai/WORKFLOW_PROTOCOL.md.
4. Lee docs/roadmap/PHASE_GOVERNANCE.md.
5. Lee docs/roadmap/CURRENT_PHASE.md.
6. Lee tasks/feature-list.json.
7. Lee specs/phases/phase-4a-legacy-scraper-consolidation.md.
8. Lee specs/features/F4A-000-legacy-parity-and-acquisition-smoke-test-strategy.md.
9. Lee docs/decisions/0016-live-vs-offline-validation.md,
   docs/decisions/0015-live-vs-offline-concurrency.md y
   docs/decisions/0004-rate-limited-scraping.md.
10. Lee progress/current.md, progress/history.md, progress/review.md y
    progress/blockers.md.
11. Revisa git status, git branch --show-current y git rev-parse HEAD.

Contexto confirmado:
- Phase 4A esta activa.
- current_phase_id debe ser phase-4a-legacy-scraper-consolidation.
- current_phase_status debe ser in_progress.
- F4A-000 debe estar done.
- F4A-001 debe seguir pending y depende de F4A-000.
- F4A-002 debe seguir pending.
- F4-001, F4-002 y F4-003 deben seguir pending.
- No debe haber tareas approved, in_progress ni needs_review.
- Validacion F4A-000:
  - python -m json.tool tasks/feature-list.json: passed.
  - uv run ruff check .: passed.
  - uv run pytest: passed, 43 passed and 3 Peewee deprecation warnings.
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed.
  - C:\Program Files\Git\bin\bash.exe scripts/harness/close.sh: passed.
- F4A-000 cerro solo la estrategia de parity offline y smoke manual; no
  implemento consolidacion legacy.
- La branch local fue creada desde b2c9960cc969bfc4c718cffd6534e6a46245704e.
- Hay cambios locales de documentacion/estado de Phase 4A sin commit.
- El cambio local preexistente en specs/phases/phase-2-scraper-cache-integration.md
  no pertenece a F4A-000; no lo edites, no lo reviertas y no lo incluyas en
  ningun commit salvo aprobacion explicita del owner.

Restricciones:
- No live scraping.
- No contactar Basketball Reference.
- No ejecutar python scrape_main.py.
- No controlled raw HTML backfill.
- No escribir DB real/dev.
- No aplicar migraciones.
- No borrar datos, raw HTML, exports, legacy ni Peewee.
- No implementar API/frontend/OVR/rankings/similarity/ML.
- No activar Phase 4 SQLAlchemy migration.
- No aprobar ni empezar F4A-001, F4A-002 ni tareas F4 sin aprobacion explicita.
- No crear commit, push ni PR sin aprobacion explicita.
- No reset, checkout, clean, stash ni descartar cambios locales.

Tarea inicial:
- Confirma desde archivos y Git que Phase 4A esta activa, F4A-000 esta done y
  no hay tareas aprobadas/en progreso/en review.
- Resume el working tree y distingue los cambios de F4A-000 del cambio
  preexistente en specs/phases/phase-2-scraper-cache-integration.md.
- Propone el siguiente paso seguro: pedir aprobacion explicita para promover
  F4A-001, o pedir aprobacion para preparar commit/PR de la activacion de
  Phase 4A y cierre de F4A-000.
- No implementes F4A-001 todavia.
```
