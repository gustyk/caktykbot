"""MongoDB index management and automatic creation.

This module handles index creation for all collections,
based on Phase 2 (Database Schema Verification) analysis.
"""

from loguru import logger
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import OperationFailure

from db.connection import get_database


def create_stocks_indexes(db: Database) -> None:
    """Create indexes for stocks collection.

    Indexes:
        - symbol (unique): Primary lookup key
        - sector (removed): Low cardinality, not needed for 20 docs
        - is_active (removed): Low cardinality, not needed for 20 docs

    Args:
        db: MongoDB database instance
    """
    collection = db.stocks

    try:
        # Unique index on symbol
        collection.create_index(
            [("symbol", ASCENDING)],
            unique=True,
            name="symbol_unique",
            background=False,  # M0 doesn't support background indexes
        )
        logger.info("✅ Created index: stocks.symbol (unique)")

    except OperationFailure as e:
        if "already exists" in str(e).lower():
            logger.debug("Index stocks.symbol already exists")
        else:
            logger.error(f"Failed to create index stocks.symbol: {e}")
            raise


def create_daily_prices_indexes(db: Database) -> None:
    """Create indexes for daily_prices collection.

    Indexes:
        - (symbol, date) compound unique: Prevents duplicates, enables fast queries
        - fetched_at: Operational queries (when was this last updated?)

    Args:
        db: MongoDB database instance
    """
    collection = db.daily_prices

    try:
        # Compound unique index on (symbol, date)
        collection.create_index(
            [("symbol", ASCENDING), ("date", DESCENDING)],
            unique=True,
            name="symbol_date_unique",
            background=False,
        )
        logger.info("✅ Created index: daily_prices.(symbol, date) (unique)")

    except OperationFailure as e:
        if "already exists" in str(e).lower():
            logger.debug("Index daily_prices.(symbol, date) already exists")
        else:
            logger.error(f"Failed to create index daily_prices.(symbol, date): {e}")
            raise

    try:
        # Index on fetched_at for operational queries
        collection.create_index(
            [("fetched_at", DESCENDING)],
            name="fetched_at_desc",
            background=False,
        )
        logger.info("✅ Created index: daily_prices.fetched_at")

    except OperationFailure as e:
        if "already exists" in str(e).lower():
            logger.debug("Index daily_prices.fetched_at already exists")
        else:
            logger.error(f"Failed to create index daily_prices.fetched_at: {e}")
            raise


def create_pipeline_runs_indexes(db: Database) -> None:
    """Create indexes for pipeline_runs collection.

    Indexes:
        - date (descending): Time-series queries

    Args:
        db: MongoDB database instance
    """
    collection = db.pipeline_runs

    try:
        # Index on date for time-series queries
        collection.create_index(
            [("date", DESCENDING)],
            name="date_desc",
            background=False,
        )
        logger.info("✅ Created index: pipeline_runs.date")

    except OperationFailure as e:
        if "already exists" in str(e).lower():
            logger.debug("Index pipeline_runs.date already exists")
        else:
            logger.error(f"Failed to create index pipeline_runs.date: {e}")
            raise


def create_trades_indexes(db: Database) -> None:
    """Create indexes for trades collection."""
    collection = db.trades
    try:
        # Index filtering by status (open/closed)
        collection.create_index(
            [("status", ASCENDING)],
            name="status_asc",
            background=False,
        )
        logger.info("✅ Created index: trades.status")
        
        # Index for looking up trades by strategy
        collection.create_index(
            [("strategy", ASCENDING)],
            name="strategy_asc",
            background=False,
        )
    except OperationFailure as e:
        logger.error(f"Failed to create indexes for trades: {e}")


def create_signals_indexes(db: Database) -> None:
    """Create indexes for signals collection."""
    collection = db.signals
    try:
        # Compound: symbol + date (unique)
        collection.create_index(
            [("symbol", ASCENDING), ("date", DESCENDING)],
            unique=True,
            name="symbol_date_unique",
            background=False,
        )
        logger.info("✅ Created index: signals.(symbol, date)")
        
        # Index for filtering active signals by date
        collection.create_index(
            [("date", DESCENDING)],
            name="date_desc",
            background=False,
        )
    except OperationFailure as e:
        logger.error(f"Failed to create indexes for signals: {e}")

def create_portfolio_indexes(db: Database) -> None:
    """Create indexes for portfolio_config."""
    collection = db.portfolio_config
    try:
        collection.create_index(
            [("user", ASCENDING)],
            unique=True,
            name="user_unique",
            background=False,
        )
        logger.info("✅ Created index: portfolio_config.user")
    except OperationFailure as e:
        logger.error(f"Failed to create indexes for portfolio: {e}")


def setup_indexes() -> None:
    """Create all indexes for all collections.

    This function should be called during application initialization
    or as a one-time setup script.

    Raises:
        Exception: If index creation fails
    """
    logger.info("Setting up MongoDB indexes...")

    try:
        db = get_database()

        # Create indexes for each collection
        create_stocks_indexes(db)
        create_daily_prices_indexes(db)
        create_pipeline_runs_indexes(db)
        create_trades_indexes(db)
        create_signals_indexes(db)
        create_portfolio_indexes(db)

        logger.info("✅ All indexes created successfully")

    except Exception as e:
        logger.error(f"Failed to setup indexes: {e}")
        raise


def list_indexes() -> dict[str, list[dict]]:
    """List all indexes for all collections.

    Returns:
        Dictionary mapping collection names to list of index information

    Example:
        {
            "stocks": [
                {"name": "symbol_unique", "key": [("symbol", 1)], "unique": True},
                ...
            ],
            ...
        }
    """
    db = get_database()
    collections = ["stocks", "daily_prices", "pipeline_runs", "trades", "signals", "portfolio_config"]

    indexes_info = {}

    for collection_name in collections:
        collection = db[collection_name]
        indexes = list(collection.list_indexes())
        indexes_info[collection_name] = indexes

    return indexes_info


def drop_all_indexes() -> None:
    """Drop all indexes (except _id) for all collections.

    WARNING: This is a destructive operation. Use only for testing or maintenance.
    """
    logger.warning("Dropping all indexes...")

    db = get_database()
    collections = ["stocks", "daily_prices", "pipeline_runs", "trades", "signals", "portfolio_config"]

    for collection_name in collections:
        collection = db[collection_name]
        try:
            # Drop all indexes except _id
            collection.drop_indexes()
            logger.info(f"Dropped indexes for collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to drop indexes for {collection_name}: {e}")


if __name__ == "__main__":
    # Allow running this module directly to setup indexes
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    
    from config.logging import setup_logging

    setup_logging()
    setup_indexes()

    # Print index information
    logger.info("\nCurrent indexes:")
    indexes = list_indexes()
    for collection, index_list in indexes.items():
        logger.info(f"\n{collection}:")
        for idx in index_list:
            logger.info(f"  - {idx['name']}: {idx.get('key', [])}")
