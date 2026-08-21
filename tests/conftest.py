import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _restore_nba_data_logger_state() -> None:
    """Undo whatever `configure_logging` did during a test.

    A test that exercises the CLI callback or the API lifespan attaches a
    stream handler bound to that test's captured `sys.stderr`. Left in place,
    it leaks into later tests as noise or a write error. This keeps the
    `nba_data` logger's handlers and level as they were before each test.
    """
    logger = logging.getLogger("nba_data")
    handlers_before = list(logger.handlers)
    level_before = logger.level
    yield
    logger.handlers[:] = handlers_before
    logger.setLevel(level_before)
