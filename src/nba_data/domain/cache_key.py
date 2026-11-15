"""The stored form of `cache_path` lineage: a key relative to the cache root.

`cache_path` never holds an absolute or OS-specific path. It holds the path of
the cached file that was actually read, relative to `SCRAPER_CACHE_DIR`, with
`/` separators, so the same page has the same key on every machine, worktree,
and OS. The absolute path is `SCRAPER_CACHE_DIR / key`.

The grammar is enforced twice: here, before a loader writes, and by a `CHECK`
constraint on every lineage table (revision `0013`). Both use the same pattern;
`tests/unit/test_cache_key.py` pins them together.
"""

from __future__ import annotations

import re

# One segment starts with a letter or digit, so `.`, `..` and empty segments
# are impossible; no drive letter (`:`), no leading `/`, no `\`.
_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9._-]*"
CACHE_KEY_PATTERN = rf"^{_SEGMENT}(/{_SEGMENT})*\.html\.gz$"
"""Shared by Python and the PostgreSQL `~` operator: the syntax is common to both."""

_CACHE_KEY_RE = re.compile(CACHE_KEY_PATTERN)


class InvalidCacheKeyError(ValueError):
    """A `cache_path` value is not a relative cache key."""


def is_cache_key(value: str) -> bool:
    return _CACHE_KEY_RE.fullmatch(value) is not None


def require_cache_key(value: str) -> str:
    """Return `value` unchanged if it is a valid cache key; raise otherwise."""

    if not isinstance(value, str) or not is_cache_key(value):
        msg = (
            "cache_path must be a path relative to the cache root with '/' "
            f"separators ending in .html.gz, got {value!r}"
        )
        raise InvalidCacheKeyError(msg)
    return value


__all__ = [
    "CACHE_KEY_PATTERN",
    "InvalidCacheKeyError",
    "is_cache_key",
    "require_cache_key",
]
