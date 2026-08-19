---
id: F4E-015
title: Populate real team names from cached team pages
areas:
  - scraping
  - data-quality
  - documentation
  - testing
priority: 80
depends_on:
  - F5-006
read:
  - docs/architecture/API_CONTRACT.md
  - src/nba_data/scraping/parsers/team_season.py
  - src/nba_data/scraping/normalizers/team_season.py
  - src/nba_data/scraping/loaders/team_season.py
  - src/nba_data/scraping/offline_processor.py
  - src/nba_data/scraping/offline_loader.py
  - src/nba_data/scraping/offline_backfill.py
  - src/nba_data/db/repositories/core.py
validation:
  - uv run pytest tests/unit/test_team_season_parser.py tests/unit/test_team_season_normalizer.py
  - uv run pytest tests/unit/test_offline_processor.py tests/unit/test_offline_backfill.py tests/unit/test_offline_loader.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Extract the real team name from the cached team page and carry it through the
team-season pipeline, so `core.teams.current_name` and `core.team_aliases.name`
stop being copies of the abbreviation. The selector is specified as an explicit
contract, because the page structure has now been measured rather than guessed.

# Evidence and current state

## The plumbing exists; the mapping that feeds it has no producer

`TeamSeasonLoadBatch.team_name` is declared `str | None = None` at
[team_season.py:18](../../src/nba_data/scraping/loaders/team_season.py#L18), and
it **is** set — at
[offline_loader.py:109](../../src/nba_data/scraping/offline_loader.py#L109), from
a `team_name_by_source` mapping keyed `(team_abbreviation, season_year)`:

```python
team_name=team_name_by_source.get(
    (entry.source.team_abbreviation, entry.source.season_year)
),
```

That parameter is threaded correctly the whole way up —
[offline_loader.py:74](../../src/nba_data/scraping/offline_loader.py#L74) →
[offline_backfill.py:70](../../src/nba_data/scraping/offline_backfill.py#L70) →
`run_full_offline_backfill`. **The defect is that no production caller ever
populates it.** The only invocation,
[main.py:205](../../src/nba_data/cli/main.py#L205), passes `cache`, `session`, and
`max_workers` and omits `team_name_by_source` entirely, so it defaults to `None`
and then to `{}`, and every `.get` returns `None`.

The deeper cause is upstream of that: `process_offline_team_season_sources` never
extracts a team name from the page, so there is nothing for the CLI to pass even
if it wanted to. **This is a missing producer and a missing hand-off, not a
missing field** — an earlier revision of this card claimed nothing in `src/` ever
sets `team_name`, which is wrong and would have sent the implementer to patch a
loader that is already correct.

`CoreRepository.get_or_create_team` therefore takes its fallback branch
(`creation_name = name or abbreviation`,
[core.py:56](../../src/nba_data/db/repositories/core.py#L56)) and
`get_or_create_team_alias` records the abbreviation as the alias name. All 775
team-season alias rows carry a name that is really an abbreviation.

## `API_CONTRACT.md` documents a value that has never existed

[API_CONTRACT.md](../../docs/architecture/API_CONTRACT.md) shows the teams example as
`"current_abbreviation": "ATL", "current_name": "Atlanta Hawks"`. Given the
above, the served value is `"ATL"`. The example has never been true.

## The team-page `<h1>` structure, measured over the whole cache

Parsed from all 775 cached team pages in
`data/raw/html/basketball-reference/teams-*.html.gz`:

- **775 of 775** pages have exactly **three** `<span>` elements in the `<h1>` —
  not two.
- The spans are, in order: the season label, **the team name**, and the literal
  `"Roster and Stats"`. The third span is `"Roster and Stats"` on all 775 pages.
- The name to store is therefore the **second** span.
- The cache covers **37 distinct team codes** across seasons 2000–2025, and
  **every code resolves to exactly one distinct name** over all its pages —
  e.g. `SEA` → *Seattle SuperSonics* (2000–2008), `OKC` → *Oklahoma City
  Thunder* (2009–2025), `NJN` → *New Jersey Nets* (2000–2012), `BRK` →
  *Brooklyn Nets* (2013–2025).

## Do not reuse `utils/team_name_abbrev.py`

It maps **name → abbreviation**, the opposite of what is needed; it lives outside
`src/nba_data/` and is imported only by the legacy `scrap/` and `db_manager/`
trees, never by the current pipeline; and it contains errors, including the key
`'Charlote Hornets Old'` for `CHH`. It is not a source of truth for team names.

# Human decisions or resources

- None.

# Acceptance criteria

- The team-page parser exposes the `<h1>` team name under an explicit,
  documented selector contract: an `<h1>` containing exactly three spans, of
  which the **second** is the team name.
- Malformed pages — no `<h1>`, a span count other than three, or an empty second
  span — produce a **recorded, named issue** in the parse/normalize result and
  leave the name unset. They must never fall back silently to the abbreviation
  and must never raise an unhandled exception.
- **A missing name is non-fatal to the page.** The team-season stats on a
  malformed page still load; only the name is absent, and the existing
  `creation_name = name or abbreviation` fallback applies. Blocking the whole
  page would trade 100% of one season's stats for a cosmetic field, and would
  make a Basketball Reference layout change an outage rather than a degradation.
  The named issue is what makes the degradation visible.
- **The derived name wins over a caller-supplied `team_name_by_source` entry**
  when both are present, and a disagreement between them is a recorded issue
  naming both values. The mapping parameter stays for tests and for callers with
  a curated override, but production data derived from the page is the default
  authority, so no caller can silently pin a stale name.
- The processor carries the extracted name on its entry results, so a
  `team_name_by_source` mapping keyed `(team_abbreviation, season_year)` can be
  built from a processing report without re-reading the cache.
- `run_full_offline_backfill` builds that mapping and passes it to
  `load_offline_team_season_report`, and the `backfill offline` CLI command
  reaches the populated path with no new flag — the existing
  `team_name_by_source` parameters are used, not replaced.
- A test asserts the end-to-end hand-off: a processing report with a parsed name
  produces a `TeamSeasonLoadBatch` whose `team_name` is that name, and
  `get_or_create_team` receives it.
- A test asserts the three-span contract against at least two **checked-in
  fixtures** from different eras, plus one fixture per malformed shape (no
  `<h1>`, two spans, four spans, empty second span). Copy the two real pages into
  `tests/fixtures/` and trim them to the `<h1>`; `data/` is untracked and listed
  as never-commit in `AGENTS.md`, so a test reading it directly passes locally
  and fails in CI.
- A test asserts that a team whose stored `current_name` currently equals its
  abbreviation is upgraded when a real name arrives, exercising the existing
  `_is_fallback_or_empty` branch at
  [core.py:64](../../src/nba_data/db/repositories/core.py#L64).
- The `API_CONTRACT.md` teams example is corrected, or annotated to state
  precisely what current data contains until a rebuild runs.
- No database writes, no migration, no backfill run as part of this card.

# Scope

- `src/nba_data/scraping/parsers/team_season.py` — the `<h1>` selector contract.
- `src/nba_data/scraping/normalizers/team_season.py` — carrying the name through.
- `src/nba_data/scraping/offline_processor.py` — recording the parsed name on the
  entry result, so the mapping can be derived from a processing report. **This is
  where the name currently dies.**
- `src/nba_data/scraping/offline_backfill.py` — building `team_name_by_source`
  from the processing report and passing it to the loader.
- `src/nba_data/cli/main.py` — the `backfill offline` call at line 205, which must
  reach the populated path.
- `src/nba_data/scraping/offline_loader.py` — read to confirm the existing
  mapping contract; expected to need **no change**.
- `docs/architecture/API_CONTRACT.md` — the example.
- `tests/fixtures/` — the two real team-page `<h1>` fixtures and the four
  malformed shapes.
- `tests/unit/` for the selector contract, the malformed shapes, the derived-name
  precedence rule, and the processor→backfill→loader hand-off.

# Out of scope

Repairing the 775 already-degraded rows, which needs a backfill and belongs to
the future rebuild-and-diff and in-place remediation cards. Deciding what a
public team *is*, which is F5-006. Franchise
lineage across codes, which is F5-008. Touching `utils/team_name_abbrev.py` or
anything in the legacy `scrap/` tree.

# Impact

`core.teams.current_name` and `core.team_aliases.name` for every future load;
the teams API response body; the team-season pipeline documentation. The
abbreviation columns and all keys are unchanged, so this is additive at the
schema level.

# Implementation notes

`depends_on: F5-006` because the team-identity decision determines whether one
name per code is the right model at all — but the extraction itself is
independent, and every measured code maps to exactly one name, so no
effective-dating is required for this archive (see F5-008).

Specify the selector as a contract, not as a scrape that happens to work: the
point of this card is that a future page-structure change fails loudly instead of
re-degrading names to abbreviations.

# Durable knowledge updates

- `docs/validation/TEAM_SEASON_PIPELINE.md` — record the measured `<h1>`
  three-span contract and the malformed-page failure behavior.
- `docs/architecture/API_CONTRACT.md` — correct the teams example.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command: `uv run pytest tests/unit/test_team_season_parser.py tests/unit/test_team_season_normalizer.py`
- Result: 17 passed.
- Command: `uv run pytest tests/unit/test_offline_processor.py tests/unit/test_offline_backfill.py tests/unit/test_offline_loader.py`
- Result: 30 passed.
- Command: `uv run pytest tests/unit/test_team_season_loader.py`
- Result: 10 passed.
- Command: `uv run ruff check .`
- Result: All checks passed.
- Command: `uv run pytest`
- Result: 727 passed, 22 skipped, 7 warnings. The skipped tests are the existing integration/service-gated cases.
- Command: `uv run mypy src/nba_data`
- Result: The same 8 pre-existing errors in 6 files; this task adds no new source typing errors.
- Command: `uv run python scripts/validate_tasks.py` with the card in `tasks/review/`
- Result: Task validation passed.

## Manual happy path

1. Run `uv run pytest tests/unit/test_team_season_parser.py -k three_span` to parse the checked-in Boston and Oklahoma City headings.
2. Run `uv run pytest tests/unit/test_offline_backfill.py -k hands_derived_name` to process cached HTML through the backfill and loader.
3. Run `uv run pytest tests/unit/test_team_season_loader.py -k upgrades_existing` to exercise a second load over abbreviation-valued team and alias rows.

Expected result:

The parser returns the second heading span as `team_name`, the processing report
carries it, the core team plus alias rows contain the derived name, and an
idempotent rerun upgrades both existing abbreviation fallbacks.

## Manual sad path

1. Run `uv run pytest tests/unit/test_team_season_parser.py -k contract_issues` against the no-heading, two-span, four-span, and empty-name fixtures.
2. Run `uv run pytest tests/unit/test_offline_processor.py -k nonfatal_contract_issue` against the existing stats fixture with no `<h1>`.
3. Run `uv run pytest tests/unit/test_offline_backfill.py -k "fallback_when_page_name_is_malformed or disagreement"` with a curated fallback and a stale caller mapping.

Expected result:

Each malformed shape records its named `team_name_*` issue and leaves the name
unset; valid stats still validate/load; a curated value supplies the name only
when parsing cannot; and a derived name wins over a stale caller value while
recording both values in the disagreement issue. The serialized processing
report includes total and per-code issue counts without making them fatal.

## Known limitations

- Existing rows already loaded with abbreviation-as-name are not remediated by
  this card; a future rebuild/remediation run is still required.
- `uv run mypy src/nba_data` remains outside this card and currently reports 8
  source-wide pre-existing typing errors, including the known BeautifulSoup
  typing issues in the team-season parser.
