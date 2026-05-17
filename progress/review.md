# Review Notes

## Phase 1 Review

Status: approved

Phase 1 foundations are approved for closure. The previous tracking blocker was
resolved by narrowing `.gitignore`, adding the required repo memory files to
Git, and strengthening the harness so required files must be present, unignored,
and tracked.

## Resolved Findings

- Required Phase 1 docs, specs, task/progress memory, harness scripts, and
  Codex prompts are no longer ignored by Git.
- `README.md` is included as a tracked Phase 1 file.
- `scripts/harness/init.sh` now checks required file existence, ignore status,
  and tracking status when running inside a Git worktree.
- `scripts/harness/validate.sh` now runs init checks before Ruff and Pytest.

## Automated Checks

- `.\.local\start-dev.ps1`: passed; no live scraping was run.
- `uv run ruff check .`: passed.
- `uv run pytest`: 13 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Notes

- No live scraping was run.
- No request to Basketball Reference was made.
- No commit or push was performed.
- `bash` in the default PowerShell PATH may point to the Windows WSL launcher;
  Git Bash is installed at `C:\Program Files\Git\bin\bash.exe` and can run the
  harness scripts.

## Phase 2 F2-001 Review

Status: approved

`F2-001` is approved for closure. The cache-first team-season helper is
additive, keeps legacy scraper code untouched, and is covered by offline tests
using fakes and local fixtures.

## Phase 2 F2-001 Checks

- `.\.local\start-dev.ps1`: passed; no live scraping was run.
- `uv run ruff check .`: passed.
- `uv run pytest`: 18 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Phase 2 F2-002 Review

Status: approved

`F2-002` is approved for closure. The cached parser helper reads only through
`HtmlCache`, raises `FileNotFoundError` on cache miss, and passes the cached
HTML string to the pure parser without accepting a client or touching the
database.

## Phase 2 F2-002 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 21 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Phase 2 F2-003 Review

Status: approved

`F2-003` is approved for closure. The realistic team-season fixture is compact,
local, and hand-authored rather than a raw downloaded dump. It covers visible
roster parsing, commented wrapped `totals_stats` and `advanced` tables, multiple
player rows, and repeated `tbody` header rows. Parser and cached-flow tests stay
offline and do not contact Basketball Reference.

## Phase 2 F2-003 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 23 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.

## Phase 2 F2-004 Review

Status: approved

`F2-004` is approved for closure. The implementation adds an injectable cached
team-season HTML provider backed by the central `HtmlCache` and
`BasketballReferenceClient` path, wires it through `PlayerOperations` into the
legacy roster, totals, and advanced scrapers, and preserves legacy
loader-facing keys such as `Player`, `G`, `PTS`, and `PER`. `scrape_main.py`
was intentionally left unchanged to avoid activating live scraping or DB writes
as part of this review task.

## Phase 2 F2-004 Checks

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed.
- No live scraping was run and no request to Basketball Reference was made.

## Phase 2 F2-LIVE-001 Review

Status: needs_review

`F2-LIVE-001` is ready for review. The smoke test used the owner-approved URL
`https://www.basketball-reference.com/teams/BOS/2024.html`, routed through
`BasketballReferenceClient`, stored the HTML in `HtmlCache`, and verified that
the adapted legacy roster, totals, and advanced scrapers can read the fetched
or cached HTML.

## Phase 2 F2-LIVE-001 Result

- Cache result: miss before execution.
- Live requests: 1.
- HTTP status: 200.
- HTML chars: 928025.
- Cache path:
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`.
- Cache exists after: `True`.
- Parsed tables: `['advanced', 'roster', 'totals']`.
- Legacy roster rows: 19.
- Legacy totals rows: 19.
- Legacy advanced rows: 19.

## Phase 2 F2-LIVE-001 Checks

- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  29 passed, 3 Peewee deprecation warnings.
- No DB writes, DB migrations, historical scraping, concurrency, extra URLs,
  Peewee/legacy deletion, API/frontend/OVR work, or retry after 429 occurred.
