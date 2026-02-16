"""MongoDB connection management with thread-safe singleton pattern.

This module implements a thread-safe MongoDB connection singleton,
addressing the concurrency safety requirements from Phase 3 analysis.
"""

import threading
from typing import Any

import pymongo
from loguru import logger
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config.settings import settings
from utils.exceptions import ConnectionError as MongoConnectionError


class MongoDBConnection:
    """Thread-safe MongoDB connection singleton.

    This class ensures that only one MongoDB client instance exists
    throughout the application lifecycle, with thread-safe initialization.

    Attributes:
        _instance: Singleton instance
        _lock: Thread lock for initialization
        _client: MongoDB client
        _db: MongoDB database
    """

    _instance: "MongoDBConnection | None" = None
    _lock: threading.Lock = threading.Lock()
    _client: MongoClient | None = None
    _db: Database | None = None

    def __new__(cls) -> "MongoDBConnection":
        """Create or return singleton instance (thread-safe).

        Returns:
            MongoDBConnection instance
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize MongoDB connection (lazy initialization)."""
        # Only initialize once
        if self._client is None:
            with self._lock:
                # Double-check locking pattern
                if self._client is None:
                    self._connect()

    def _connect(self) -> None:
        """Establish MongoDB connection with retry logic.

        Raises:
            MongoConnectionError: If connection fails after retries
        """
        max_retries = 3
        retry_delay = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Connecting to MongoDB (attempt {attempt}/{max_retries})..."
                )

                # Create MongoDB client
                self._client = MongoClient(
                    settings.MONGO_URI,
                    serverSelectionTimeoutMS=5000,  # 5 seconds timeout
                    connectTimeoutMS=10000,  # 10 seconds connection timeout
                    socketTimeoutMS=30000,  # 30 seconds socket timeout
                    maxPoolSize=10,  # Connection pool size
                    minPoolSize=1,
                    maxIdleTimeMS=45000,  # 45 seconds max idle time
                )

                # Test connection
                self._client.admin.command("ping")

                # Get database
                self._db = self._client[settings.MONGO_DB_NAME]

                logger.info(
                    f"✅ MongoDB connected successfully (database: {settings.MONGO_DB_NAME})"
                )
                return

            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.warning(
                    f"MongoDB connection attempt {attempt}/{max_retries} failed: {e}"
                )

                if attempt == max_retries:
                    logger.critical(
                        "Failed to connect to MongoDB after all retries. "
                        "Check MONGO_URI and network connectivity."
                    )
                    raise MongoConnectionError(
                        f"Failed to connect to MongoDB after {max_retries} attempts: {e}"
                    ) from e

                # Wait before retry (except on last attempt)
                if attempt < max_retries:
                    import time

                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

            except Exception as e:
                logger.critical(f"Unexpected error during MongoDB connection: {e}")
                raise MongoConnectionError(
                    f"Unexpected MongoDB connection error: {e}"
                ) from e

    def get_database(self) -> Database:
        """Get MongoDB database instance.

        Returns:
            MongoDB database instance

        Raises:
            MongoConnectionError: If database is not initialized
        """
        if self._db is None:
            raise MongoConnectionError("MongoDB database not initialized")
        return self._db

    def get_client(self) -> MongoClient:
        """Get MongoDB client instance.

        Returns:
            MongoDB client instance

        Raises:
            MongoConnectionError: If client is not initialized
        """
        if self._client is None:
            raise MongoConnectionError("MongoDB client not initialized")
        return self._client

    def close(self) -> None:
        """Close MongoDB connection.

        This should only be called during application shutdown.
        """
        if self._client is not None:
            with self._lock:
                if self._client is not None:
                    self._client.close()
                    self._client = None
                    self._db = None
                    logger.info("MongoDB connection closed")

    def ping(self) -> bool:
        """Test MongoDB connection.

        Returns:
            True if connection is alive, False otherwise
        """
        try:
            if self._client is None:
                return False
            self._client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False


# Global connection instance
_connection: MongoDBConnection | None = None
_connection_lock: threading.Lock = threading.Lock()


def get_connection() -> MongoDBConnection:
    """Get global MongoDB connection instance (thread-safe).

    Returns:
        MongoDBConnection instance
    """
    global _connection

    if _connection is None:
        with _connection_lock:
            # Double-check locking pattern
            if _connection is None:
                _connection = MongoDBConnection()

    return _connection


def get_database() -> Database:
    """Get MongoDB database instance (convenience function).

    Returns:
        MongoDB database instance
    """
    return get_connection().get_database()


def get_client() -> MongoClient:
    """Get MongoDB client instance (convenience function).

    Returns:
        MongoDB client instance
    """
    return get_connection().get_client()


def close_connection() -> None:
    """Close MongoDB connection (convenience function).

    This should only be called during application shutdown.
    """
    global _connection

    if _connection is not None:
        _connection.close()
        _connection = None
# Aliases for backward compatibility or different naming conventions
MongoManager = MongoDBConnection
