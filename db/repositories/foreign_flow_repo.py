from datetime import datetime, timezone
from typing import List, Optional

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING

from db.schemas import ForeignFlowBase, ForeignFlowInDB


class ForeignFlowRepository:
    """Repository for managing foreign flow data in MongoDB."""

    def __init__(self, db: Database) -> None:
        """Initialize repository.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection: Collection = db.foreign_flow
        # Ensure indexes
        self.collection.create_index([("symbol", ASCENDING), ("date", DESCENDING)], unique=True)
        # TTL Index
        self.collection.create_index("created_at", expireAfterSeconds=180 * 24 * 60 * 60)

    def add_flow(self, flow_data: ForeignFlowBase) -> ForeignFlowInDB:
        """Add or update foreign flow record.

        Args:
            flow_data: Data to add

        Returns:
            The created document
        """
        data_dict = flow_data.model_dump()
        data_dict["created_at"] = datetime.now(timezone.utc)
        
        result = self.collection.find_one_and_update(
            {
                "symbol": flow_data.symbol,
                "date": flow_data.date
            },
            {"$set": data_dict},
            upsert=True,
            return_document=True
        )
        
        return ForeignFlowInDB(**result)

    def get_flow(self, symbol: str, date: datetime) -> Optional[ForeignFlowInDB]:
        """Get foreign flow for a symbol on a specific date.

        Args:
            symbol: Ticker symbol
            date: Date to filter

        Returns:
            Document or None
        """
        doc = self.collection.find_one({"symbol": symbol, "date": date})
        if not doc:
            return None
        return ForeignFlowInDB(**doc)

    def get_history(self, symbol: str, limit: int = 30) -> List[ForeignFlowInDB]:
        """Get foreign flow history for a symbol.

        Args:
            symbol: Ticker symbol
            limit: Number of days

        Returns:
            List of documents sorted by date DESC
        """
        cursor = self.collection.find({"symbol": symbol}).sort("date", DESCENDING).limit(limit)
        return [ForeignFlowInDB(**doc) for doc in cursor]
