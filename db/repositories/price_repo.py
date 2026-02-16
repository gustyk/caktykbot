"""Daily price repository for MongoDB.

This module implements the repository pattern for the 'daily_prices' collection,
ensuring referential integrity and efficient retrieval of historical data.
"""

from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection
from pymongo.database import Database

from db.schemas import DailyPriceBase, DailyPriceInDB
from utils.exceptions import PriceRepoError, ReferentialIntegrityError


class PriceRepository:
    """Repository for managing daily stock prices in MongoDB."""

    def __init__(self, db: Database) -> None:
        """Initialize repository.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection: Collection = db.daily_prices
        self.stocks_collection: Collection = db.stocks

    def upsert_price(self, price_data: DailyPriceBase) -> DailyPriceInDB:
        """Insert or update a daily price record.

        Ensures referential integrity by checking if the stock exists.

        Args:
            price_data: Price data to save

        Returns:
            The saved price document

        Raises:
            ReferentialIntegrityError: If symbol is not in stocks collection
            PriceRepoError: If database operation fails
        """
        # Validate referential integrity
        if not self.stocks_collection.find_one({"symbol": price_data.symbol}):
            raise ReferentialIntegrityError(
                f"Cannot add price for '{price_data.symbol}': Stock not in watchlist"
            )

        now = datetime.now(timezone.utc)
        price_dict = price_data.model_dump()
        
        # Build filter for upsert (symbol + date)
        # We ensure date is at midnight for consistency if needed, 
        # but here we rely on the schema's validation
        query = {
            "symbol": price_data.symbol,
            "date": price_data.date
        }

        # Update if exists, insert if not
        result = self.collection.find_one_and_update(
            query,
            {"$set": {**price_dict, "fetched_at": now}},
            upsert=True,
            return_document=True
        )

        if not result:
            raise PriceRepoError(f"Failed to upsert price for {price_data.symbol} on {price_data.date}")

        return DailyPriceInDB(**result)

    def bulk_upsert_prices(self, prices_data: list[dict]) -> int:
        """Bulk insert or update price records.
        
        Args:
           prices_data: List of price dicts (enriched)
           
        Returns:
           Count of operations
        """
        if not prices_data:
            return 0
            
        from pymongo import UpdateOne
        
        operations = []
        now = datetime.now(timezone.utc)
        
        for p in prices_data:
            query = {"symbol": p["symbol"], "date": p["date"]}
            update = {"$set": {**p, "fetched_at": now}}
            operations.append(UpdateOne(query, update, upsert=True))
            
        if operations:
            result = self.collection.bulk_write(operations, ordered=False)
            return result.upserted_count + result.modified_count
        return 0

    def get_latest_price(self, symbol: str) -> Optional[DailyPriceInDB]:
        """Get the most recent price record for a stock.

        Args:
            symbol: Ticker symbol

        Returns:
            DailyPriceInDB instance or None if no data
        """
        doc = self.collection.find_one(
            {"symbol": symbol},
            sort=[("date", -1)]
        )
        if not doc:
            return None
        return DailyPriceInDB(**doc)

    def get_historical_prices(
        self, 
        symbol: str, 
        limit: int = 250,
        start_date: Optional[datetime] = None
    ) -> list[DailyPriceInDB]:
        """Get historical prices for a stock.

        Args:
            symbol: Ticker symbol
            limit: Maximum records to return (default 250 for EMA200 calculation)
            start_date: Optional start date filter

        Returns:
            List of DailyPriceInDB instances sorted by date descending
        """
        query = {"symbol": symbol}
        if start_date:
            query["date"] = {"$gte": start_date}

        cursor = self.collection.find(query).sort("date", -1).limit(limit)
        return [DailyPriceInDB(**doc) for doc in cursor]

    def delete_all_for_stock(self, symbol: str) -> int:
        """Delete all price records for a specific stock.

        Args:
            symbol: Ticker symbol

        Returns:
            Number of deleted records
        """
        result = self.collection.delete_many({"symbol": symbol})
        return result.deleted_count
