"""Stock repository for MongoDB.

This module implements the repository pattern for the 'stocks' collection,
handling data access logic and ensuring strict schema enforcement and error handling.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.collection import Collection
from pymongo.database import Database

from db.schemas import StockCreate, StockInDB, StockUpdate
from utils.exceptions import DuplicateStockError, StockNotFoundError, WatchlistFullError


class StockRepository:
    """Repository for managing stock watchlist in MongoDB."""

    def __init__(self, db: Database, max_watchlist: int = 100) -> None:
        """Initialize repository.

        Args:
            db: MongoDB database instance
            max_watchlist: Maximum allowed stocks in watchlist
        """
        self.db = db
        self.collection: Collection = db.stocks
        self.max_watchlist = max_watchlist

    def add_stock(self, stock_data: StockCreate) -> StockInDB:
        """Add a new stock to the watchlist.

        Args:
            stock_data: Stock data to add

        Returns:
            The created stock document

        Raises:
            WatchlistFullError: If maximum capacity is reached
            DuplicateStockError: If symbol already exists
        """
        # Check capacity
        count = self.collection.count_documents({})
        if count >= self.max_watchlist:
            raise WatchlistFullError(f"Watchlist full (max {self.max_watchlist} stocks)")

        # Check existing
        if self.collection.find_one({"symbol": stock_data.symbol}):
            raise DuplicateStockError(f"Stock {stock_data.symbol} already in watchlist")

        now = datetime.now(timezone.utc)
        stock_dict = stock_data.model_dump()
        stock_dict.update({
            "added_at": now,
            "updated_at": now
        })

        self.collection.insert_one(stock_dict)
        return StockInDB(**stock_dict)

    def get_stock(self, symbol: str) -> Optional[StockInDB]:
        """Get a stock by symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            StockInDB instance or None if not found
        """
        doc = self.collection.find_one({"symbol": symbol})
        if not doc:
            return None
        return StockInDB(**doc)

    def get_all_stocks(self, only_active: bool = True) -> list[StockInDB]:
        """Get all stocks in watchlist.

        Args:
            only_active: Whether to return only active stocks

        Returns:
            List of StockInDB instances
        """
        query = {"is_active": True} if only_active else {}
        cursor = self.collection.find(query).sort("symbol", 1)
        return [StockInDB(**doc) for doc in cursor]

    def update_stock(self, symbol: str, update_data: StockUpdate) -> StockInDB:
        """Update an existing stock.

        Args:
            symbol: Ticker symbol
            update_data: Data to update

        Returns:
            The updated stock document

        Raises:
            StockNotFoundError: If stock doesn't exist
        """
        # Update timestamp
        update_dict = update_data.model_dump(exclude_unset=True)
        if not update_dict:
             # Just return existing if nothing to update
             stock = self.get_stock(symbol)
             if not stock:
                 raise StockNotFoundError(f"Stock {symbol} not found")
             return stock

        update_dict["updated_at"] = datetime.now(timezone.utc)

        result = self.collection.find_one_and_update(
            {"symbol": symbol},
            {"$set": update_dict},
            return_document=True
        )

        if not result:
            raise StockNotFoundError(f"Stock {symbol} not found")

        return StockInDB(**result)

    def delete_stock(self, symbol: str) -> bool:
        """Delete a stock from watchlist.

        Args:
            symbol: Ticker symbol

        Returns:
            True if deleted, False if not found
        """
        result = self.collection.delete_one({"symbol": symbol})
        return result.deleted_count > 0

    def deactivate_stock(self, symbol: str) -> StockInDB:
        """Deactivate a stock (set is_active=False).

        Args:
            symbol: Ticker symbol

        Returns:
            The updated stock document

        Raises:
            StockNotFoundError: If stock doesn't exist
        """
        return self.update_stock(symbol, StockUpdate(is_active=False))

