"""The `basketball_reference_player_id` shape: the single source of truth.

Acquisition validation (`scraping/player_page_acquisition.py`) and offline
player-page cache discovery (`scraping/player_page_cache.py`) both build their
matching patterns from `PLAYER_ID_PATTERN` rather than restating the range, so
the two ends of the pipeline cannot drift apart — F4E-012 fixed exactly that
drift once already.

This module imports nothing beyond the standard library: like
`domain/team_codes.py`, it stays a leaf so any pure, database-free consumer
(such as `validation/stats_coverage.py`) can depend on it without pulling in
SQLAlchemy, ORM models, or the scraping HTTP client transitively.
"""

from __future__ import annotations

PLAYER_ID_MIN_LENGTH = 6
PLAYER_ID_MAX_LENGTH = 10
PLAYER_ID_PATTERN = rf"[a-z][a-z0-9]{{{PLAYER_ID_MIN_LENGTH - 1},{PLAYER_ID_MAX_LENGTH - 1}}}"

__all__ = [
    "PLAYER_ID_MAX_LENGTH",
    "PLAYER_ID_MIN_LENGTH",
    "PLAYER_ID_PATTERN",
]
