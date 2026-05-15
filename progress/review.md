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
