# F1-007 - Rate Limited Client

## Goal

Add the central Basketball Reference HTTP client.

## Context

Legacy scrapers currently make direct requests with local sleeps.

## Requirements

- Add sync client with default 10 requests/minute and 6 second delay.
- Require user agent.
- Respect `Retry-After`.
- Back off on 5xx.
- Raise clear error on repeated 429.
- Use cache when provided.

## Acceptance Criteria

- Tests use mocked HTTP only.
- Client API exposes `get(url, *, force_refresh=False) -> str`.

## Validation

- `uv run pytest tests/unit/test_rate_limited_client.py`

## Out of Scope

- Adapting legacy scrapers.

## Learning Notes

Centralizing HTTP makes policy enforceable.
