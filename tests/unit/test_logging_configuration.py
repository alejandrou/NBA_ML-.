import logging
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from nba_data.api import create_app
from nba_data.cli.main import app as cli_app
from nba_data.config.logging_config import PACKAGE_LOGGER_NAME, configure_logging
from nba_data.config.settings import Settings, get_settings
from nba_data.scraping.client import BasketballReferenceClient


@pytest.mark.unit
def test_configure_logging_is_idempotent() -> None:
    settings = Settings(log_level="INFO", _env_file=None)

    configure_logging(settings)
    configure_logging(settings)

    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr


@pytest.mark.unit
def test_configure_logging_applies_the_configured_level() -> None:
    settings = Settings(log_level="WARNING", _env_file=None)

    logger = configure_logging(settings)

    assert logger.level == logging.WARNING


@pytest.mark.unit
def test_configure_logging_format_carries_required_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(log_level="INFO", _env_file=None)
    logger = configure_logging(settings)

    logger.info("a distinctive message")

    captured = capsys.readouterr()
    assert "a distinctive message" in captured.err
    assert "INFO" in captured.err
    assert PACKAGE_LOGGER_NAME in captured.err


@pytest.mark.unit
def test_importing_nba_data_never_configures_logging() -> None:
    """Importing the CLI and API modules must leave the logging system untouched."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import logging\n"
            "import nba_data.cli.main\n"
            "import nba_data.api.app\n"
            "logger = logging.getLogger('nba_data')\n"
            "assert logger.handlers == [], logger.handlers\n"
            "print('OK')\n",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


@pytest.mark.unit
def test_cli_callback_configures_logging() -> None:
    get_settings.cache_clear()
    result = CliRunner().invoke(cli_app, ["info"])

    assert result.exit_code == 0
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    assert len(logger.handlers) == 1


@pytest.mark.unit
def test_api_lifespan_configures_logging() -> None:
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app):
        logger = logging.getLogger(PACKAGE_LOGGER_NAME)
        assert len(logger.handlers) == 1


@pytest.mark.unit
def test_cache_hit_emits_a_formatted_info_line(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(log_level="INFO", _env_file=None)
    configure_logging(settings)

    class _StubCache:
        def get(self, url: str) -> str | None:
            return "<html>cached</html>"

        def set(self, url: str, html: str) -> None:  # pragma: no cover - not exercised
            raise AssertionError("no network write expected on a cache hit")

    client = BasketballReferenceClient(settings, cache=_StubCache())  # type: ignore[arg-type]

    with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
        html = client.get("https://www.basketball-reference.com/players/j/jamesle01.html")

    assert html == "<html>cached</html>"
    assert any("HTML cache hit" in record.message for record in caplog.records)
