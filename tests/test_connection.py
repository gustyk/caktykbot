"""Tests for MongoDB connection management."""

import threading
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from db.connection import (
    MongoDBConnection,
    close_connection,
    get_client,
    get_connection,
    get_database,
)
from utils.exceptions import ConnectionError as MongoConnectionError


class TestMongoDBConnection:
    """Test MongoDB connection singleton."""

    def test_singleton_pattern(self):
        """Test that MongoDBConnection is a singleton."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            # Create two instances
            conn1 = MongoDBConnection()
            conn2 = MongoDBConnection()

            # Should be the same instance
            assert conn1 is conn2

    def test_thread_safe_initialization(self):
        """Test that singleton initialization is thread-safe."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            instances = []

            def create_connection():
                conn = MongoDBConnection()
                instances.append(conn)

            # Create connections from multiple threads
            threads = [threading.Thread(target=create_connection) for _ in range(10)]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # All instances should be the same
            assert all(inst is instances[0] for inst in instances)

    def test_successful_connection(self):
        """Test successful MongoDB connection."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            conn = MongoDBConnection()

            # Should have called MongoClient
            mock_client.assert_called_once()

            # Should have tested connection with ping
            mock_client_instance.admin.command.assert_called_with("ping")

    def test_connection_retry_logic(self):
        """Test connection retry with exponential backoff."""
        with patch("db.connection.MongoClient") as mock_client:
            with patch("time.sleep") as mock_sleep:
                # Mock connection failure on first 2 attempts, success on 3rd
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance

                call_count = 0

                def ping_side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count < 3:
                        raise ServerSelectionTimeoutError("Connection timeout")
                    return {"ok": 1}

                mock_client_instance.admin.command.side_effect = ping_side_effect

                # Reset singleton
                MongoDBConnection._instance = None
                MongoDBConnection._client = None
                MongoDBConnection._db = None

                conn = MongoDBConnection()

                # Should have retried 3 times
                assert call_count == 3

                # Should have slept between retries (2 times: after 1st and 2nd attempt)
                assert mock_sleep.call_count == 2

    def test_connection_failure_after_retries(self):
        """Test connection failure after all retries exhausted."""
        with patch("db.connection.MongoClient") as mock_client:
            with patch("time.sleep"):
                # Mock connection failure on all attempts
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance
                mock_client_instance.admin.command.side_effect = ServerSelectionTimeoutError(
                    "Connection timeout"
                )

                # Reset singleton
                MongoDBConnection._instance = None
                MongoDBConnection._client = None
                MongoDBConnection._db = None

                with pytest.raises(MongoConnectionError, match="Failed to connect"):
                    MongoDBConnection()

    def test_get_database(self):
        """Test get_database() returns database instance."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}
            mock_db = MagicMock()
            mock_client_instance.__getitem__.return_value = mock_db

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            conn = MongoDBConnection()
            db = conn.get_database()

            assert db is not None

    def test_get_database_not_initialized(self):
        """Test get_database() raises error if not initialized."""
        # Create instance without initializing database
        conn = MongoDBConnection.__new__(MongoDBConnection)
        conn._client = None
        conn._db = None

        with pytest.raises(MongoConnectionError, match="not initialized"):
            conn.get_database()

    def test_get_client(self):
        """Test get_client() returns client instance."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            conn = MongoDBConnection()
            client = conn.get_client()

            assert client is mock_client_instance

    def test_ping_success(self):
        """Test ping() returns True when connection is alive."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            conn = MongoDBConnection()
            result = conn.ping()

            assert result is True

    def test_ping_failure(self):
        """Test ping() returns False when connection fails."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful initial connection but failed ping
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            call_count = 0

            def ping_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"ok": 1}  # Initial connection
                raise ConnectionFailure("Ping failed")  # Subsequent ping

            mock_client_instance.admin.command.side_effect = ping_side_effect

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            conn = MongoDBConnection()
            result = conn.ping()

            assert result is False

    def test_close_connection(self):
        """Test close() closes MongoDB connection."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            conn = MongoDBConnection()
            conn.close()

            # Should have called close on client
            mock_client_instance.close.assert_called_once()

            # Client and db should be None
            assert conn._client is None
            assert conn._db is None

    def test_global_get_connection(self):
        """Test global get_connection() function."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            # Reset global connection
            import db.connection

            db.connection._connection = None

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            conn1 = get_connection()
            conn2 = get_connection()

            # Should be the same instance
            assert conn1 is conn2

    def test_global_get_database(self):
        """Test global get_database() function."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}
            mock_db = MagicMock()
            mock_client_instance.__getitem__.return_value = mock_db

            # Reset global connection
            import db.connection

            db.connection._connection = None

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            db = get_database()

            assert db is not None

    def test_global_close_connection(self):
        """Test global close_connection() function."""
        with patch("db.connection.MongoClient") as mock_client:
            # Mock successful connection
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            mock_client_instance.admin.command.return_value = {"ok": 1}

            # Reset global connection
            import db.connection

            db.connection._connection = None

            # Reset singleton
            MongoDBConnection._instance = None
            MongoDBConnection._client = None
            MongoDBConnection._db = None

            # Create connection
            get_connection()

            # Close it
            close_connection()

            # Global connection should be None
            assert db.connection._connection is None
