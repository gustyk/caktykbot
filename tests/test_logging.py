"""Tests for logging configuration."""

from unittest.mock import patch, MagicMock
from config.logging import setup_logging, get_logger
import sys

@patch("config.logging.settings")
def test_setup_logging_development(mock_settings):
    mock_settings.ENVIRONMENT = "development"
    mock_settings.LOG_LEVEL = "INFO"
    with patch("config.logging.logger.add") as mock_add:
        with patch("config.logging.logger.remove") as mock_remove:
            setup_logging()
            mock_remove.assert_called_once()
            # development has 2 adds: file and stdout
            assert mock_add.call_count == 2

@patch("config.logging.settings")
def test_setup_logging_production(mock_settings):
    mock_settings.ENVIRONMENT = "production"
    mock_settings.LOG_LEVEL = "INFO"
    with patch("config.logging.logger.add") as mock_add:
        with patch("config.logging.logger.remove") as mock_remove:
            setup_logging()
            mock_remove.assert_called_once()
            assert mock_add.call_count == 1

@patch("config.logging.settings")
def test_setup_logging_test(mock_settings):
    mock_settings.ENVIRONMENT = "test"
    with patch("config.logging.logger.add") as mock_add:
        with patch("config.logging.logger.remove") as mock_remove:
            setup_logging()
            mock_remove.assert_called_once()
            assert mock_add.call_count == 1

@patch("config.logging.settings")
def test_setup_logging_fallback(mock_settings):
    mock_settings.ENVIRONMENT = "unknown"
    with patch("config.logging.logger.add") as mock_add:
        with patch("config.logging.logger.remove") as mock_remove:
            setup_logging()
            mock_remove.assert_called_once()
            assert mock_add.call_count == 1

def test_get_logger():
    assert get_logger() is not None
