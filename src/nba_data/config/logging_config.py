"""Logging configuration for the `nba_data` package logger.

This is the only place in `src/` that touches global logging state. Every
module in the package logs through `logging.getLogger(__name__)`, so
configuring the `nba_data` package logger (rather than the root logger) covers
all of them without taking over logging for dependencies or for a host
application that imports this package.

`configure_logging` must never be called at import time — only from the CLI's
Typer callback and the API's FastAPI lifespan, so importing `nba_data` leaves
the logging system untouched.
"""

from __future__ import annotations

import logging
import sys

from nba_data.config.settings import Settings

PACKAGE_LOGGER_NAME = "nba_data"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

_HANDLER_NAME = "nba_data.stderr"


def configure_logging(settings: Settings) -> logging.Logger:
    """Apply `settings.log_level` to the `nba_data` logger.

    Idempotent: calling this twice re-applies the level but attaches at most
    one stream handler, identified by name, so log lines are never doubled.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.setLevel(settings.log_level)

    existing = next(
        (handler for handler in logger.handlers if handler.name == _HANDLER_NAME), None
    )
    if existing is None:
        handler = logging.StreamHandler(sys.stderr)
        handler.name = _HANDLER_NAME
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)

    return logger
