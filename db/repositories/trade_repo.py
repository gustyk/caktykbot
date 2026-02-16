"""Repository for Trade Management."""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from pymongo.database import Database
from pymongo import DESCENDING

from db.schemas import Trade, TradeLeg

logger = logging.getLogger(__name__)


class TradeRepository:
    """Repository for managing trades in MongoDB."""

    def __init__(self, db: Database):
        self.collection = db.trades
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create indexes for common queries."""
        self.collection.create_index([("symbol", 1), ("entry_date", -1)])
        self.collection.create_index([("status", 1), ("entry_date", -1)])
        self.collection.create_index([("user", 1), ("entry_date", -1)])

    def insert_trade(self, trade: Trade) -> str:
        """Insert a new trade."""
        result = self.collection.insert_one(trade.model_dump())
        return str(result.inserted_id)

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID."""
        # Need ObjectId import if we query by _id
        from bson.objectid import ObjectId
        try:
            doc = self.collection.find_one({"_id": ObjectId(trade_id)})
            if doc:
                return Trade(**doc)
        except Exception:
            return None
        return None

    def get_open_trades(self, symbol: Optional[str] = None, user: str = "nesa") -> List[Trade]:
        """Get all open trades for user, optionally filtered by symbol."""
        query = {"user": user, "status": "open"}
        if symbol:
            query["symbol"] = symbol
        
        cursor = self.collection.find(query).sort("entry_date", DESCENDING)
        return [Trade(**doc) for doc in cursor]
    
    def get_draft_trades(self, symbol: Optional[str] = None, user: str = "nesa") -> List[Trade]:
        """Get draft trades."""
        query = {"user": user, "status": "draft"}
        if symbol:
            query["symbol"] = symbol
            
        cursor = self.collection.find(query).sort("created_at", DESCENDING)
        return [Trade(**doc) for doc in cursor]

    def get_all_closed_trades(self, user: str = "nesa") -> List[Trade]:
        """Get all closed trades for user."""
        cursor = self.collection.find({"user": user, "status": "closed"}).sort("exit_date", DESCENDING)
        return [Trade(**doc) for doc in cursor]

    def get_last_trades(self, limit: int = 10, user: str = "nesa") -> List[Trade]:
        """Get last N trades (mixed status)."""
        cursor = self.collection.find({"user": user}).sort("entry_date", DESCENDING).limit(limit)
        return [Trade(**doc) for doc in cursor]
        
    def get_all_trades(self, user: str = "nesa") -> List[Trade]:
         """Get all trades for user."""
         cursor = self.collection.find({"user": user}).sort("entry_date", DESCENDING)
         return [Trade(**doc) for doc in cursor]

    def update_trade_fields(self, trade_id: str, updates: Dict[str, Any]) -> bool:
        """Generic update for trade fields."""
        from bson.objectid import ObjectId
        updates["updated_at"] = datetime.now()
        
        result = self.collection.update_one(
            {"_id": ObjectId(trade_id)},
            {"$set": updates}
        )
        return result.modified_count > 0

    def add_leg(self, trade_id: str, leg: TradeLeg, remaining_qty: int) -> bool:
        """Add a partial exit leg and update remaining qty."""
        from bson.objectid import ObjectId
        
        update = {
            "$push": {"legs": leg.model_dump()},
            "$set": {
                "qty_remaining": remaining_qty,
                "updated_at": datetime.now()
            }
        }
        
        result = self.collection.update_one(
            {"_id": ObjectId(trade_id)},
            update
        )
        return result.modified_count > 0
        
    def close_trade(self, trade_id: str, final_data: Dict[str, Any]) -> bool:
        """Mark trade as closed with final stats."""
        from bson.objectid import ObjectId
        final_data["status"] = "closed"
        final_data["qty_remaining"] = 0
        final_data["updated_at"] = datetime.now()
        
        result = self.collection.update_one(
            {"_id": ObjectId(trade_id)},
            {"$set": final_data}
        )
        return result.modified_count > 0
