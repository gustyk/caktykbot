from datetime import datetime, timezone
from typing import List, Optional

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING

from db.schemas import BrokerSummaryBase, BrokerSummaryInDB


class BrokerRepository:
    """Repository for managing broker summary data in MongoDB."""

    def __init__(self, db: Database) -> None:
        """Initialize repository.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection: Collection = db.broker_summary
        # Ensure indexes
        self.collection.create_index([("symbol", ASCENDING), ("date", DESCENDING)])
        self.collection.create_index([("symbol", ASCENDING), ("broker_code", ASCENDING), ("date", DESCENDING)])
        # TTL Index - expire after 180 days (approx 6 months)
        self.collection.create_index("created_at", expireAfterSeconds=180 * 24 * 60 * 60)

    def add_summary(self, summary_data: BrokerSummaryBase) -> BrokerSummaryInDB:
        """Add a new broker summary record.

        Args:
            summary_data: Data to add

        Returns:
            The created document
        """
        data_dict = summary_data.model_dump()
        data_dict["created_at"] = datetime.now(timezone.utc)
        
        # Upsert based on symbol, date, broker_code
        result = self.collection.find_one_and_update(
            {
                "symbol": summary_data.symbol,
                "date": summary_data.date,
                "broker_code": summary_data.broker_code
            },
            {"$set": data_dict},
            upsert=True,
            return_document=True
        )
        
        return BrokerSummaryInDB(**result)

    def add_summaries(self, summaries: List[BrokerSummaryBase]) -> int:
        """Bulk add broker summaries.
        
        Args:
            summaries: List of data to add
            
        Returns:
            Count of inserted/updated records
        """
        count = 0
        for summary in summaries:
            self.add_summary(summary)
            count += 1
        return count

    def get_by_date(self, symbol: str, date: datetime) -> List[BrokerSummaryInDB]:
        """Get broker summaries for a symbol on a specific date.

        Args:
            symbol: Ticker symbol
            date: Date to filter

        Returns:
            List of documents
        """
        cursor = self.collection.find({"symbol": symbol, "date": date})
        return [BrokerSummaryInDB(**doc) for doc in cursor]

    def get_latest(self, symbol: str, limit: int = 5) -> List[BrokerSummaryInDB]:
        """Get latest broker summaries for a symbol (latest dates).
        
        Note: This returns the summaries for the most recent DATE, effectively top brokers for that day.
        Or, if we want history for a specific broker, we'd need another method.
        Assuming this is "Get top brokers for most recent available data".
        
        Args:
            symbol: Ticker symbol
            limit: Limit (not strictly applied if we fetch by date group, but here simple find)
            
        Returns:
            List of documents
        """
        # Find latest date first
        latest = self.collection.find_one({"symbol": symbol}, sort=[("date", DESCENDING)])
        if not latest:
            return []
            
        latest_date = latest["date"]
        return self.get_by_date(symbol, latest_date)

    def get_broker_history(self, symbol: str, broker_code: str, days: int = 30) -> List[BrokerSummaryInDB]:
        """Get history of a specific broker for a symbol.
        
        Args:
            symbol: Ticker symbol
            broker_code: Broker code (e.g. YP)
            days: Num days lookback
            
        Returns:
            List of documents sorted by date desc
        """
        cursor = self.collection.find(
            {"symbol": symbol, "broker_code": broker_code}
        ).sort("date", DESCENDING).limit(days)
        
        return [BrokerSummaryInDB(**doc) for doc in cursor]
