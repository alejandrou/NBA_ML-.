# F1-008 - HTML Cache

## Goal

Add compressed raw HTML cache.

## Context

Future parsers and tests should reuse raw source HTML without repeat downloads.

## Requirements

- Store `.html.gz`.
- Generate stable URL keys.
- Keep paths under the configured cache root.
- Provide `get`, `set`, `exists`, and `path_for_url`.

## Acceptance Criteria

- Cache tests pass using temporary directories.

## Validation

- `uv run pytest tests/unit/test_html_cache.py`

## Out of Scope

- Remote object storage.

## Learning Notes

Cache is the first defense against unnecessary web traffic.
