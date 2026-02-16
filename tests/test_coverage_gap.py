"""Comprehensive coverage and stability tests for CakTykBot Core."""

import os
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from config.settings import Settings, get_settings, settings
from db.connection import (
    MongoDBConnection,
    close_connection,
    get_client,
    get_connection,
    get_database,
    MongoManager
)
from db.repositories.pipeline_repo import PipelineRepository
from db.repositories.price_repo import PriceRepository
from db.repositories.stock_repo import StockRepository
from db.indexes import setup_indexes
from scheduler.jobs import SchedulerManager, run_pipeline_job
from utils.exceptions import ConnectionError as MongoConnectionError


class TestCoreCoverageGaps:
    """Tests designed to fill coverage gaps in core infrastructure."""

    def test_settings_singleton_init_failure(self, monkeypatch):
        """Test get_settings failure handling."""
        # Reset global settings
        import config.settings
        monkeypatch.setattr(config.settings, "_settings", None)
        
        # Mock Settings() to fail
        with patch("config.settings.Settings", side_effect=Exception("Load failed")):
            with pytest.raises(SystemExit) as e:
                get_settings()
            assert e.value.code == 1

    def test_settings_proxy_attribute_access(self):
        """Test SettingsProxy lazy attribute access."""
        # Ensure it works even if not directly initialized
        # access any field
        assert settings.MONGO_DB_NAME == "caktykbot"

    def test_mongo_connection_get_client_error(self):
        """Test get_client error when not initialized."""
        conn = MongoDBConnection.__new__(MongoDBConnection)
        conn._client = None
        with pytest.raises(MongoConnectionError, match="client not initialized"):
            conn.get_client()

    def test_mongo_connection_close_none(self):
        """Test close() when client is already None."""
        conn = MongoDBConnection.__new__(MongoDBConnection)
        conn._client = None
        conn._lock = threading.Lock()
        conn.close() # Should not raise

    def test_mongo_connection_ping_none(self):
        """Test ping() when client is None."""
        conn = MongoDBConnection.__new__(MongoDBConnection)
        conn._client = None
        assert conn.ping() is False

    def test_global_get_database_convenience(self):
        """Test global convenience function for database."""
        with patch("db.connection.get_connection") as mock_get_conn:
            mock_db = MagicMock()
            mock_get_conn.return_value.get_database.return_value = mock_db
            assert get_database() is mock_db

    def test_global_get_client_convenience(self):
        """Test global convenience function for client."""
        with patch("db.connection.get_connection") as mock_get_conn:
            mock_client = MagicMock()
            mock_get_conn.return_value.get_client.return_value = mock_client
            assert get_client() is mock_client

    def test_mongo_manager_alias(self):
        """Test that MongoManager is just an alias for MongoDBConnection."""
        assert MongoManager is MongoDBConnection

    def test_pipeline_repo_get_history_empty(self, mongo_test_db):
        """Test pipeline repo history when empty."""
        repo = PipelineRepository(mongo_test_db)
        history = repo.get_history()
        assert history == []

    def test_stock_repo_update_missing(self, mongo_test_db):
        """Test updating a stock that doesn't exist."""
        from utils.exceptions import StockNotFoundError
        from db.schemas import StockUpdate
        repo = StockRepository(mongo_test_db)
        with pytest.raises(StockNotFoundError):
            repo.update_stock("NONEXISTENT.JK", StockUpdate(is_active=False))

