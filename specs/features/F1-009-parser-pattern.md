# F1-009 - Parser Pattern

## Goal

Add an example pure parser for a Basketball Reference team-season page.

## Context

Legacy scrapers mix fetching, parsing, and persistence.

## Requirements

- Parser receives HTML string.
- Parser returns structured data.
- Parser supports tables hidden inside HTML comments.
- Parser does not use network or DB.
- Add minimal fixture HTML.

## Acceptance Criteria

- Parser test proves roster, totals, and advanced tables can be read.

## Validation

- `uv run pytest tests/unit/test_team_season_parser.py`

## Out of Scope

- Full parser migration.

## Learning Notes

Pure parsers are easy to test and reuse.
