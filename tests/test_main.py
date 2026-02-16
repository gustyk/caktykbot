"""Smoke tests for the main entry point."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from main import main


def test_main_help():
    """Test that help command works."""
    with patch.object(sys, 'argv', ['main.py', '--help']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0


def test_main_check(monkeypatch):
    """Test the check command."""
    mock_db = MagicMock()
    # Mocking setup_repositories dependencies
    monkeypatch.setattr("main.setup_repositories", lambda: {})
    
    with patch.object(sys, 'argv', ['main.py', 'check']):
        main() # Should not raise exit


@patch("main.run_sync")
def test_main_sync(mock_run_sync):
    """Test that sync command calls run_sync."""
    with patch.object(sys, 'argv', ['main.py', 'sync']):
        main()
        assert mock_run_sync.called


@patch("main.start_app")
def test_main_start(mock_start_app):
    """Test that start command calls start_app."""
    with patch.object(sys, 'argv', ['main.py', 'start']):
        main()
        assert mock_start_app.called
